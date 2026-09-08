#!/usr/bin/env python3
from __future__ import annotations
import copy
import t6_seal6_blender_role_plan_v1 as mod


def fixture():
    materials=[]; bind=[]; tex=[]
    for mi,(name,count) in enumerate(mod.TARGETS.items()):
        roles=[]; slots=[]
        for i in range(count):
            semantic='normalMap' if i==min(2,count-1) else 'colorMap'
            image=f'img_{mi}_{i}'
            row={'index':i,'semantic':semantic,'name':f'role_{i}','image':image,'samplerState':{'filter':'linear'},'nativeRecord':{'semantic':semantic,'name':f'role_{i}','image':image}}
            roles.append(row)
            slots.append({'index':i,'semanticName':semantic,'image':image})
            tex.append({'image':image,'repository':'base.ipak','nameHash':i,'dataHash':i+1,'iwiSha256':'a'*64,'pngSha256':'b'*64,'pngFile':f'{image}.png','crc29Validated':True,'exactKeyValidated':True})
        materials.append({'material':name,'physicalCopyCount':1,'activeRetailClientOwnerResolved':True,'byteIdenticalAcrossCopies':True,'techniqueSetIdenticalAcrossCopies':True,'textureRecordsStructurallyIdenticalAcrossCopies':True,'copies':[{'techniqueSet':'mc/test','textureRoleRows':roles}]})
        bind.append({'material':name,'slots':slots,'gltfVisualization':{'baseColor':{'slotIndex':0,'image':roles[0]['image']},'normal':{'slotIndex':min(2,count-1),'image':roles[min(2,count-1)]['image']},'shaderApproximation':True}})
    conflict={'format':mod.CONFLICT_FORMAT,'materials':materials}
    binding={'format':mod.BINDING_FORMAT,'materials':bind}
    materialized={'format':'t6-ipak-iwi-materialization-v3','textures':tex}
    return conflict,binding,materialized


def main()->int:
    c,b,m=fixture();r=mod.build(c,b,m)
    assert r['summary']['targetMaterials']==5
    assert r['summary']['nativeTextureSlots']==20
    assert r['summary']['uniqueExactRetailImages']==20
    assert r['summary']['allNativeTextureSlotsRepresented'] is True
    assert r['summary']['completeRetailPixelOutput'] is False
    head=r['materials'][0]
    assert head['nativeSlotCount']==5
    assert head['nativeSlots'][0]['previewUse']==['legacy-authoring-base-color']
    assert head['nativeSlots'][2]['previewUse']==['legacy-authoring-normal']
    assert head['nativeSlots'][1]['previewUse']==[]

    bad=copy.deepcopy(c)
    bad['materials'][0]['textureRecordsStructurallyIdenticalAcrossCopies']=False
    try: mod.build(bad,b,m)
    except mod.BlenderRolePlanError as e: assert 'native texture array differs' in str(e)
    else: raise AssertionError('accepted divergent native role table')

    bad=copy.deepcopy(b)
    bad['materials'][0]['slots'][0]['image']='wrong'
    try: mod.build(c,bad,m)
    except mod.BlenderRolePlanError as e: assert 'binding image' in str(e)
    else: raise AssertionError('accepted binding/native image drift')

    bad=copy.deepcopy(m)
    bad['textures'][0]['exactKeyValidated']=False
    try: mod.build(c,b,bad)
    except mod.BlenderRolePlanError as e: assert 'exact-key/CRC29 closure' in str(e)
    else: raise AssertionError('accepted unvalidated payload')

    print('PASS t6_seal6_blender_role_plan_v1')
    return 0
if __name__=='__main__': raise SystemExit(main())
