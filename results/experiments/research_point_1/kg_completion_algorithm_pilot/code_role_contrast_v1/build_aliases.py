"""Administrative full catalogue copy blockers; not new facts or supervision."""
from role_io import *
def main():
    d=I.load();a=UF()
    for pop in [d['raw'],d['audit'],d['normalized'],d['graph']['source_records']]:
        for r in pop:
            for s in ['head','tail']:a.join('L|'+r[s+'_type']+'|'+I.norm(r[s+'_canonical_zh']),'S|'+I.norm(r[s+'_surface']))
    result=[a.find('L|'+e['entity_type']+'|'+I.norm(e['label_zh'])) for e in read(RUN/'data/catalogue.json')['entities']]
    save(NEW/'administrative_entity_aliases.json',result);print('Saved full8754 copy-blocking aliases')
if __name__=='__main__':main()
