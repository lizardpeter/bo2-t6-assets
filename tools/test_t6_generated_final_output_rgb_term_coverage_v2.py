#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_rgb_term_coverage_v2 as c

SHA='a'*64

def docs():
    # Authoritative DAG node identities 0..19. The classifier deliberately does
    # not need to reinterpret their math; term families come from prior exact sidecars.
    nodes=[{'id':i,'kind':'symbol','name':f'n{i}','args':[]} for i in range(20)]
    final={'format':c.v1.FINAL_FORMAT,'shaders':[{'sha256':SHA,'nodes':nodes}]}
    topology={'format':c.v1.TOPOLOGY_FORMAT,'shaders':[{'sha256':SHA,'techniqueSets':['lit_sm_fixture'],'lanes':{
        'x':{'outputRootNode':10,'leaves':[{'path':'ROOT','sign':1,'node':10,'anchorTags':['squareRgb','directional:0'],'resources':[]}]},
        'y':{'outputRootNode':11,'leaves':[{'path':'ROOT','sign':1,'node':11,'anchorTags':['specular:x','reflectionProbe'],'resources':['reflectionProbeSampler']}]},
        'z':{'outputRootNode':12,'leaves':[{'path':'ROOT','sign':1,'node':12,'anchorTags':['reflectionProbe'],'resources':['reflectionProbeSampler']}]},
    }}]}
    product={'format':c.v1.PRODUCT_FORMAT,'shaders':[{'sha256':SHA,'equations':[{'channels':{
        'x':{'squareNode':1,'directionalRgbNode':2,'directProduct':True,'directProductNode':10},
        'y':{'squareNode':5,'directionalRgbNode':7,'directProduct':False,'directProductNode':None},
        'z':{'squareNode':6,'directionalRgbNode':8,'directProduct':False,'directProductNode':None},
    }}]}]}
    sr={'format':c.v1.SR_FORMAT,'materials':[{'material':'*m','shaderSha256':SHA,'channels':{
        'x':[],
        'y':[{'specularRootNode':14,'mixingSiteNode':11,'reflectionSampleNode':13,'directSpecularTimesReflectionSample':True,'outputLanes':['y']}],
        'z':[], 'w':[],
    }}]}
    square={'format':c.v1.SQUARE_FORMAT,'shaders':[{'sha256':SHA,'anchors':[
        {'channel':'x','anchored':True,'candidateCount':1,'candidates':[{'squareNode':1,'encodedRgbNode':0}]},
        {'channel':'y','anchored':True,'candidateCount':1,'candidates':[{'squareNode':5,'encodedRgbNode':3}]},
        {'channel':'z','anchored':True,'candidateCount':1,'candidates':[{'squareNode':6,'encodedRgbNode':9}]},
    ]}]}
    directional={'format':c.v1.DIR_FORMAT,'shaders':[{'sha256':SHA,'equations':[{'rgbNodes':{'x':2,'y':7,'z':8},'normalNodes':{}}]}]}
    spec={'format':c.v1.SPEC_FORMAT,'materials':[{'material':'*m','shaderSha256':SHA,'finalStateNodes':{'x':14,'y':15,'z':16,'w':17}}]}
    reflection={'format':c.v1.REFL_FORMAT,'shaders':[{'shaderSha256':SHA,'samples':[
        {'sampleNodeIds':[13],'coordinateNodes':[],'extraOperandNodes':[],'classification':{'kind':'literal_lod','known':True}},
        {'sampleNodeIds':[12],'coordinateNodes':[],'extraOperandNodes':[],'classification':{'kind':'literal_lod','known':True}},
    ]}]}
    return topology,product,sr,final,square,directional,spec,reflection

def main()->int:
    d=docs();got=c.build(*d,strict=True)
    assert got['format']==c.FORMAT
    assert got['authoritativeDagPreflight']['allReferencedNodesExist'] is True
    assert got['authoritativeDagPreflight']['authoritativeShaderCount']==1
    assert got['authoritativeDagPreflight']['nodeReferenceCheckCount']>0
    s=got['summary']
    assert s['syntacticLeafCount']==3 and s['coveredLeafCount']==3 and s['unclassifiedLeafCount']==0
    assert s['fullyCoveredRgbLaneCount']==3 and s['fullyCoveredShaderCount']==1
    assert s['termFamilyCounts']=={
        'direct_specular_times_reflection':1,
        'direct_squared_rgb_times_directional':1,
        'standalone_reflection_sample':1,
    }
    lanes=got['shaders'][0]['lanes']
    assert lanes['x']['leaves'][0]['family']=='direct_squared_rgb_times_directional'
    assert lanes['y']['leaves'][0]['family']=='direct_specular_times_reflection'
    assert lanes['z']['leaves'][0]['family']=='standalone_reflection_sample'

    # Existing authoritative node, but no exact promoted term family: semantic
    # coverage is incomplete rather than a broken identity reference.
    relaxed=list(copy.deepcopy(d));relaxed[0]['shaders'][0]['lanes']['z']['leaves'][0]['node']=18;relaxed[0]['shaders'][0]['lanes']['z']['outputRootNode']=18
    q=c.build(*relaxed,strict=False)
    assert q['summary']['unclassifiedLeafCount']==1
    assert q['shaders'][0]['lanes']['z']['leaves'][0]['family']=='unclassified'
    try:c.build(*relaxed,strict=True)
    except c.v1.FinalRgbTermCoverageError as exc: assert 'strict final RGB term coverage incomplete' in str(exc)
    else:raise AssertionError('strict mode accepted an unclassified existing term')

    # Nonexistent node is a trust-boundary failure before semantic classification.
    broken=list(copy.deepcopy(d));broken[0]['shaders'][0]['lanes']['z']['leaves'][0]['node']=99
    try:c.build(*broken,strict=False)
    except c.FinalRgbTermCoverageV2Error as exc: assert 'absent authoritative DAG node 99' in str(exc)
    else:raise AssertionError('sidecar reference to nonexistent DAG node was accepted')

    print('PASS: exact generated final RGB syntactic term coverage v2')
    return 0
if __name__=='__main__':raise SystemExit(main())
