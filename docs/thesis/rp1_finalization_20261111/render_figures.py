"""Plot frozen-table quantities only; no inference, extraction or graph writes."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
plt.rcParams.update({'svg.hashsalt':'rp1-thesis-20261111','font.size':10})

def rows(name):return list(csv.DictReader((ROOT/'tables'/name).open()))
def save(fig,name):
    for suffix in ['svg','png']:fig.savefig(ROOT/'figures'/f'{name}.{suffix}',bbox_inches='tight',dpi=200,metadata={'Date':None} if suffix=='svg' else {'Software':'RP1 frozen-table report'})
    plt.close(fig)

scale={r['population']:r for r in rows('graph_scale.csv')}
names=['strict208','standard1326','expanded1456'];x=list(range(3));fig,ax=plt.subplots(figsize=(8,4))
for j,(field,label) in enumerate([('records','Evidence records'),('actual_serialized_claims','Claims'),('actual_serialized_entities','Entities')]):
    values=[int(scale[n][field]) for n in names]
    bars=ax.bar([i+(j-1)*.25 for i in x],values,width=.25,label=label)
    ax.bar_label(bars,padding=2,fontsize=8)
ax.set_xticks(x,names);ax.set_ylabel('Count (different object types)');ax.set_ylim(0,2450);ax.legend(loc='upper left');ax.set_title('Graph versions: quantities, not factual accuracy');save(fig,'graph_scale')

gate=rows('incremental_gate_ablation.csv');rep=rows('source_family_replication.csv');fig,axes=plt.subplots(1,2,figsize=(12,4))
values=[int(gate[0]['input_count'])]+[int(r['output_count']) for r in gate]
axes[0].plot(range(len(values)),values,'o-',color='#336699');axes[0].set_xticks(range(len(values)),['Input','Schema','Locate','Support','Provenance','Score','Strict ZH'],rotation=35,ha='right');axes[0].set_ylabel('Retained candidate occurrences');axes[0].set_title('Fixed 8003 candidates; historical ordered gates')
for i,v in enumerate(values):axes[0].annotate(str(v),(i,v),xytext=(0,5),textcoords='offset points',ha='center',fontsize=8)
m=[int(r['replication_multiplier']) for r in rep]
axes[1].plot(m,[float(r['family_support_mean']) for r in rep],'o-',label='Family-capped');axes[1].plot(m,[float(r['document_naive_support_mean']) for r in rep],'s--',label='Document naive');axes[1].set_xticks(m);axes[1].set_ylim(0,1);axes[1].set_xlabel('Same-family replication multiplier');axes[1].set_ylabel('Uncalibrated index mean');axes[1].set_title('Synthetic duplication, not natural corroboration');axes[1].legend()
fig.tight_layout();save(fig,'gates_and_replication')
print('Rendered two frozen-data figures in SVG and PNG.')
