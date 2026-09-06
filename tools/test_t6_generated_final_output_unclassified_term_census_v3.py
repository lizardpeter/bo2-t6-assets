#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_generated_final_output_unclassified_term_census_v3 as v3

SHA='a'*64

def base_docs():
 final={'format':v3.FINAL_FORMAT,'shaders':[{'sha256':SHA,'techniqueSets':['lit_sm_fixture'],'nodes':[
  {'id':0,'kind':'symbol','name':'cb1[59].x'},
  {'id':1,'kind':'literal32','bits':'3f800000'},
  {'id':2,'kind':'op','op':'mul','args':[0,1]},
  {'id':3,'kind':'symbol','name':'cb1[59].x'},
  {'id':4,'kind':'literal32','bits':'3f800000'},
  {'id':5,'kind':'op','op':'mul','args':[3,4]},
 ]}]}
 terms=[]
 for lane,node,cb,lit in [('x',2,0,1),('y',5,3,4)]:
  terms.append({'sha256':SHA,'techniqueSets':['lit_sm_fixture'],'lane':lane,'path':[0],'sign':1,'node':node,'kind':'op','operation':'mul','exactAnchorTags':[],'ancestryAnchorTags':[],'resources':[],'immediateChildren':[
   {'node':cb,'kind':'symbol','operation':None,'exactAnchorTags':[],'ancestryAnchorTags':[],'resources':[]},
   {'node':lit,'kind':'literal32','operation':None,'exactAnchorTags':[],'ancestryAnchorTags':[],'resources':[],'literal32Bits':'3f800000'},
  ],'structuralProfileSha256V2':'s'})
 base={'format':v3.v2.FORMAT,'terms':terms,'signatureGroups':[{'structuralProfileSha256':'s','count':2,'observedLanes':['x','y']}],'summary':{'shaderCount':1,'unclassifiedLeafCount':2,'structuralSignatureCount':1,'channelAgnosticGrouping':True},'proofBoundary':'fixture-v2'}
 ident={'symbol':'cb1[59].x','bindPoint':1,'register':59,'registerComponent':'x','registerComponentIndex':0,'byteOffset':944,'buffer':{'name':'PerMaterial','size':960,'type':0,'flags':0},'variable':{'name':'alphaRevealParms1','startOffset':944,'size':16,'endOffset':960,'relativeByteOffset':0,'relativeScalarIndex':0},'techniqueAssignments':[{'techniqueSet':'lit_sm_fixture','sourceClass':'material','sourceExpression':'material.alphaRevealParms1','sourceName':'alphaRevealParms1'}]}
 cb={'format':v3.CBUFFER_FORMAT,'shaders':[{'sha256':SHA,'usedCbufferSymbols':[{**ident,'nodeIds':[0,3],'nodeCount':2}]}],'summary':{}}
 return base,final,cb

def main()->int:
 base,final,cb=base_docs();doc=v3.build(base,final,cb)
 assert doc['format']==v3.FORMAT
 assert doc['summary']['v2StructuralSignatureCount']==1
 assert doc['summary']['cbufferEnrichedStructuralSignatureCount']==1
 assert doc['summary']['termWithCbufferDependencyCount']==2
 assert doc['summary']['termCbufferDependencyOccurrenceCount']==2
 assert doc['summary']['immediateChildCbufferDependencyOccurrenceCount']==2
 assert doc['summary']['uniqueReflectedCbufferVariableCount']==1
 assert doc['summary']['cbufferAssignmentSourceClassCounts']=={'material':2}
 assert doc['signatureGroups']==base['signatureGroups']
 assert doc['cbufferEnrichedSignatureGroups'][0]['count']==2
 assert doc['cbufferEnrichedSignatureGroups'][0]['observedLanes']==['x','y']
 for term in doc['terms']:
  dep=term['cbufferDependenciesV1'][0]
  assert dep['symbol']=='cb1[59].x'
  assert dep['variable']['name']=='alphaRevealParms1'
  assert dep['techniqueAssignments'][0]['sourceExpression']=='material.alphaRevealParms1'

 # Change only the second exact reflected identity. The old v2 group remains one,
 # while v3 must split it into two cbuffer-enriched structural families.
 base2,final2,cb2=base_docs()
 final2['shaders'][0]['nodes'][3]['name']='cb1[60].x'
 second=copy.deepcopy(cb2['shaders'][0]['usedCbufferSymbols'][0])
 cb2['shaders'][0]['usedCbufferSymbols'][0]['nodeIds']=[0]
 second.update({'symbol':'cb1[60].x','register':60,'byteOffset':960,'nodeIds':[3],'nodeCount':1})
 second['variable']={'name':'otherParameter','startOffset':960,'size':16,'endOffset':976,'relativeByteOffset':0,'relativeScalarIndex':0}
 second['techniqueAssignments']=[{'techniqueSet':'lit_sm_fixture','sourceClass':'code','sourceExpression':'code.otherParameter','sourceName':'otherParameter'}]
 cb2['shaders'][0]['usedCbufferSymbols'].append(second)
 split=v3.build(base2,final2,cb2)
 assert split['summary']['v2StructuralSignatureCount']==1
 assert split['summary']['cbufferEnrichedStructuralSignatureCount']==2
 assert split['summary']['uniqueReflectedCbufferVariableCount']==2
 assert split['summary']['cbufferAssignmentSourceClassCounts']=={'code':1,'material':1}

 # Raw DAG cbuffer symbols and the cbuffer sidecar must agree exactly.
 bad=copy.deepcopy(cb);bad['shaders'][0]['usedCbufferSymbols'][0]['symbol']='cb1[59].y'
 try:v3.build(base,final,bad)
 except v3.UnclassifiedTermCensusV3Error as exc:assert 'symbol' in str(exc)
 else:raise AssertionError('v3 accepted a cbuffer sidecar whose raw symbol disagrees with the final DAG')
 print('PASS: cbuffer-enriched unclassified final RGB census v3');return 0
if __name__=='__main__':raise SystemExit(main())
