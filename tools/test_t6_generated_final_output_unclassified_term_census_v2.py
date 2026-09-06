#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_unclassified_term_census_v2 as c

SHA='a'*64

def docs(reverse_y=False):
    nodes=[
        {'id':0,'kind':'symbol','name':'sqx','args':[]},
        {'id':1,'kind':'symbol','name':'sqy','args':[]},
        {'id':2,'kind':'symbol','name':'sqz','args':[]},
        {'id':3,'kind':'textureSample','resource':'unknownSampler','channel':'w','sampler':'unknown_s','opcode':'sample','args':[]},
        {'id':4,'kind':'op','op':'mul','args':[0,3]},
        {'id':5,'kind':'op','op':'mul','args':[3,1] if reverse_y else [1,3]},
    ]
    final={'format':c.v1.FINAL_FORMAT,'shaders':[{'sha256':SHA,'techniqueSets':['lit_sm_fixture'],'nodes':nodes}]}
    coverage={'format':c.v1.COVERAGE_FORMAT,'shaders':[{'sha256':SHA,'lanes':{
        'x':{'leaves':[{'path':'ROOT','sign':1,'node':4,'family':'unclassified'}]},
        'y':{'leaves':[{'path':'ROOT','sign':1,'node':5,'family':'unclassified'}]},
        'z':{'leaves':[{'path':'ROOT','sign':1,'node':2,'family':'standalone_squared_rgb'}]},
    }}],'summary':{'unclassifiedLeafCount':2}}
    square={'format':c.v1.SQUARE_FORMAT,'shaders':[{'sha256':SHA,'anchors':[
        {'channel':'x','anchored':True,'candidateCount':1,'candidates':[{'squareNode':0}]},
        {'channel':'y','anchored':True,'candidateCount':1,'candidates':[{'squareNode':1}]},
        {'channel':'z','anchored':True,'candidateCount':1,'candidates':[{'squareNode':2}]},
    ]}]}
    directional={'format':c.v1.DIR_FORMAT,'shaders':[{'sha256':SHA,'equations':[]}]}
    spec={'format':c.v1.SPEC_FORMAT,'materials':[]}
    reflection={'format':c.v1.REFL_FORMAT,'shaders':[{'shaderSha256':SHA,'samples':[]}]}
    return coverage,final,square,directional,spec,reflection

def main()->int:
    got=c.build(*docs(False))
    assert got['format']==c.FORMAT
    assert got['summary']['unclassifiedLeafCount']==2
    assert got['summary']['v1LaneSpecificStructuralSignatureCount']==2
    assert got['summary']['structuralSignatureCount']==1
    assert got['summary']['channelAgnosticGrouping'] is True
    group=got['signatureGroups'][0]
    assert group['count']==2 and group['observedLanes']==['x','y']
    assert 'lane' not in group['profile']
    assert [child['exactAnchorTags'] for child in group['profile']['immediateChildren']]==[['squareRgb'],[]]
    assert group['profile']['immediateChildren'][1]['resources']==['unknownSampler']
    assert len({term['structuralProfileSha256V2'] for term in got['terms']})==1

    # Operand order remains forensic and therefore splits the structural group.
    reversed_doc=c.build(*docs(True))
    assert reversed_doc['summary']['structuralSignatureCount']==2
    assert sorted(group['count'] for group in reversed_doc['signatureGroups'])==[1,1]

    bad=list(copy.deepcopy(docs(False)));bad[0]['summary']['unclassifiedLeafCount']=3
    try:c.build(*bad)
    except c.v1.UnclassifiedTermCensusError as exc:assert 'unclassifiedLeafCount 3 != observed 2' in str(exc)
    else:raise AssertionError('coverage/census unclassified count mismatch accepted')

    print('PASS: channel-agnostic unclassified final RGB term census v2')
    return 0
if __name__=='__main__':raise SystemExit(main())
