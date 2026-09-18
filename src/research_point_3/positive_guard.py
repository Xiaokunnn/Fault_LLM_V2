"""Train-only safeguard on actual optimizer displacement, not raw Adam gradients."""
import copy
from contextlib import contextmanager
import math
import time


@contextmanager
def deterministic_reference_mode(model):
    states=[(module,module.training) for module in model.modules()]
    model.eval()
    try:
        yield
    finally:
        for module,state in states:
            module.training=state


def positive_reference_loss(model, reference):
    import torch.nn.functional as F
    mask=reference['availability_mask'] & reference['requested_candidate_mask'] & (reference['support_labels']==1)
    if not mask.any():
        raise ValueError('positive guard requires assessed available requested-role positives')
    output=model(reference['query_features'],reference['candidate_features'],reference['availability_mask'],reference['selection_budget'])
    return F.softplus(-output.support_logits[mask]).mean()


def project_displacement(displacement, gradients, margin):
    """Closest displacement in g.v <= -margin*||g||*||d||, Euclidean metric."""
    import torch
    if not 0 < margin < 1 or len(displacement)!=len(gradients) or not displacement:
        raise ValueError('aligned vectors and margin in (0,1) required')
    dot=sum(float((d.double()*g.double()).sum()) for d,g in zip(displacement,gradients))
    g2=sum(float(g.double().square().sum()) for g in gradients)
    d2=sum(float(d.double().square().sum()) for d in displacement)
    if not all(math.isfinite(v) for v in (dot,g2,d2)):
        raise ValueError('nonfinite proposed displacement or reference gradient')
    bound=-margin*math.sqrt(g2*d2)
    coefficient=max(dot-bound,0.0)/g2 if g2 else 0.0
    projected=tuple(d-coefficient*g for d,g in zip(displacement,gradients))
    actual_dot=sum(float((v.double()*g.double()).sum()) for v,g in zip(projected,gradients))
    return projected, {'proposal_dot':dot,'projected_dot':actual_dot,'halfspace_bound':bound,
        'gradient_norm':math.sqrt(g2),'proposal_norm':math.sqrt(d2),'projection_coefficient':coefficient,
        'projected':coefficient>0}


class PositiveStepGuard:
    def __init__(self, reference, *, margin=.1, backtracks=8, tolerance=1e-7):
        if not 0<margin<1 or type(backtracks) is not int or backtracks<0 or not math.isfinite(tolerance) or tolerance<0:
            raise ValueError('invalid positive guard constants')
        self.reference=reference
        self.margin=margin
        self.backtracks=backtracks
        self.tolerance=tolerance
        self.positive_count=int((reference['availability_mask'] & reference['requested_candidate_mask'] & (reference['support_labels']==1)).sum())
        if self.positive_count==0:raise ValueError('no eligible positive reference labels')

    def step(self, model, optimizer):
        """Base gradients are already populated/clipped; auxiliary autograd does not change them."""
        import torch
        start=time.perf_counter()
        parameters=tuple(model.parameters())
        before=tuple(p.detach().clone() for p in parameters)
        optimizer_before=copy.deepcopy(optimizer.state_dict())
        with deterministic_reference_mode(model):
            before_loss=positive_reference_loss(model,self.reference)
            gradients=torch.autograd.grad(before_loss,parameters,allow_unused=True)
            gradients=tuple(g.detach() if g is not None else torch.zeros_like(p) for g,p in zip(gradients,parameters))
            before_value=float(before_loss.detach())
            if not math.isfinite(before_value):raise RuntimeError('nonfinite positive reference before update')
            try:
                optimizer.step()
                raw=tuple(p.detach()-old for p,old in zip(parameters,before))
                projected,geometry=project_displacement(raw,gradients,self.margin)
                trials=[];accepted=False;after=before_value;scale=0.
                for k in range(self.backtracks+1):
                    candidate_scale=2.0**(-k)
                    with torch.no_grad():
                        for p,old,v in zip(parameters,before,projected):p.copy_(old+candidate_scale*v)
                        value=float(positive_reference_loss(model,self.reference))
                    trials.append({'scale':candidate_scale,'positive_loss':value if math.isfinite(value) else None})
                    if math.isfinite(value) and value<=before_value+self.tolerance:
                        accepted=True;after=value;scale=candidate_scale;break
                if not accepted:
                    with torch.no_grad():
                        for p,old in zip(parameters,before):p.copy_(old)
                    optimizer.load_state_dict(optimizer_before)
            except Exception:
                with torch.no_grad():
                    for p,old in zip(parameters,before):p.copy_(old)
                optimizer.load_state_dict(optimizer_before)
                raise
        return {**geometry,'accepted':accepted,'scale':scale,'positive_loss_before':before_value,
            'positive_loss_after':after,'positive_loss_change':after-before_value,'tolerance':self.tolerance,
            'trial_count':len(trials),'trials':trials,'reference_forward_calls':1+len(trials),
            'positive_reference_count':self.positive_count,'seconds':time.perf_counter()-start,
            'optimizer_state_restored':not accepted}
