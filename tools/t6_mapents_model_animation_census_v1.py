#!/usr/bin/env python3
"""Map-agnostic T6 MapEnts model/animation census.

Parses the raw entityString owned by a T6 MapEnts asset and emits a deterministic
JSON census of entity classes, model references, animation-scene metadata, and
script-model placements. Optional --gltf compares exact source model tokens to
node/mesh names in a candidate glTF/GLB without pretending substring matches are
proof of full semantic integration.

This is an inventory/provenance tool, not a renderer. It preserves all source
key/value pairs for relevant entities and never invents missing transforms.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, re, struct
from pathlib import Path

PAIR_RE = re.compile(r'^"((?:\\.|[^"\\])*)"\s+"((?:\\.|[^"\\])*)"\s*$')

def _unescape(s: str) -> str:
    return s.replace(r'\\"','"').replace(r'\\\\','\\')

def parse_entities(raw: bytes):
    text = raw.decode('latin1')
    ents=[]; cur=None
    for lineno,line in enumerate(text.splitlines(),1):
        s=line.strip().strip('\x00')
        if not s: continue
        if s=='{':
            if cur is not None: raise ValueError(f'nested entity at line {lineno}')
            cur={'pairs':[], 'startLine':lineno}
        elif s=='}':
            if cur is None: raise ValueError(f'orphan }} at line {lineno}')
            cur['endLine']=lineno
            kv={}
            for k,v in cur['pairs']: kv[k]=v
            cur['kv']=kv; cur['index']=len(ents); ents.append(cur); cur=None
        else:
            if cur is None: raise ValueError(f'pair outside entity at line {lineno}')
            m=PAIR_RE.match(s)
            if not m: raise ValueError(f'unparsed entity line {lineno}: {s[:120]}')
            cur['pairs'].append((_unescape(m.group(1)),_unescape(m.group(2))))
    if cur is not None: raise ValueError('unterminated entity')
    return text, ents

def parse_glb_json(path: Path):
    b=path.read_bytes()
    if b[:4]==b'glTF':
        magic,version,total=struct.unpack_from('<4sII',b,0)
        if version!=2 or total!=len(b): raise ValueError('invalid GLB header')
        n,typ=struct.unpack_from('<I4s',b,12)
        if typ!=b'JSON': raise ValueError('first GLB chunk is not JSON')
        return json.loads(b[20:20+n].decode('utf-8').rstrip(' \t\r\n\0'))
    return json.loads(b.decode('utf-8'))

def vec3(v):
    if v is None: return None
    parts=v.split()
    if len(parts)!=3: return {'raw':v,'parseError':True}
    try: return [float(x) for x in parts]
    except ValueError: return {'raw':v,'parseError':True}

def relevant_entity(e):
    k=e['kv']
    return ('model' in k or 'fxanim_scene_1' in k or 'destructibledef' in k or
            any(x.startswith('fxanim_') for x in k) or
            str(k.get('targetname','')).startswith('nuke_animated_') or
            'nuke_display_glass' in str(k.get('targetname','')))

def entity_record(e):
    k=e['kv']
    return {
        'entityIndex':e['index'], 'sourceLines':[e['startLine'],e['endLine']],
        'classname':k.get('classname'), 'model':k.get('model'),
        'origin':vec3(k.get('origin')), 'angles':vec3(k.get('angles')),
        'targetname':k.get('targetname'), 'target':k.get('target'),
        'spawnflags':k.get('spawnflags'), 'destructibledef':k.get('destructibledef'),
        'fxanimScene':k.get('fxanim_scene_1'), 'fxanimWait':k.get('fxanim_wait'),
        'fxanimWaittill':k.get('fxanim_waittill'), 'fxanimLoop':k.get('fxanim_loop'),
        'pairs':e['pairs'],
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('entity_string',type=Path)
    ap.add_argument('--map',default=None)
    ap.add_argument('--gltf',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    raw=args.entity_string.read_bytes(); text,ents=parse_entities(raw)
    classes=collections.Counter(e['kv'].get('classname','<none>') for e in ents)
    models=[e['kv']['model'] for e in ents if 'model' in e['kv']]
    model_counts=collections.Counter(models)
    brush=[m for m in models if m.startswith('*')]
    named=[m for m in models if not m.startswith('*')]
    named_counts=collections.Counter(named)
    script_models=[e for e in ents if e['kv'].get('classname')=='script_model']
    script_brush=[e for e in ents if e['kv'].get('classname')=='script_brushmodel']
    fxanim=[e for e in ents if 'fxanim_scene_1' in e['kv']]
    destructible=[e for e in script_models if 'destructibledef' in e['kv']]
    car=[e for e in script_models if 'car01' in e['kv'].get('model','') or 'car02' in e['kv'].get('model','')]
    animated_car=[e for e in car if e['kv'].get('targetname','').startswith('nuke_animated_car')]
    parked_car=[e for e in car if 'destructibledef' in e['kv']]
    display=[e for e in ents if 'display_glass' in e['kv'].get('model','') or 'nuke_display_glass' in e['kv'].get('targetname','')]

    gltf=None
    if args.gltf:
        d=parse_glb_json(args.gltf)
        node_names=[n.get('name','') for n in d.get('nodes',[])]
        mesh_names=[m.get('name','') for m in d.get('meshes',[])]
        hay='\n'.join(node_names+mesh_names)
        exact_named=[]; substring_named=[]
        for m in sorted(named_counts):
            exact = (m in node_names or m in mesh_names)
            substring = m in hay
            exact_named.append(m) if exact else None
            substring_named.append(m) if substring else None
        gltf={
            'file':args.gltf.name,'bytes':args.gltf.stat().st_size,
            'sha256':hashlib.sha256(args.gltf.read_bytes()).hexdigest(),
            'nodes':len(d.get('nodes',[])),'meshes':len(d.get('meshes',[])),
            'skins':len(d.get('skins',[])),'animations':len(d.get('animations',[])),
            'exactNamedMapEntModelTokensFound':exact_named,
            'substringNamedMapEntModelTokensFound':substring_named,
            'substringNamedMapEntModelTokenCount':len(substring_named),
            'namedMapEntModelTokenCount':len(named_counts),
            'note':'Substring presence is an inventory hint only; it is not proof that the MapEnt entity instance/phase/gameplay semantics are integrated.'
        }

    out={
        'format':'t6-mapents-model-animation-census-v1', 'map':args.map,
        'source':{'file':args.entity_string.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},
        'counts':{
            'entities':len(ents),'classCounts':dict(classes.most_common()),
            'modelReferences':len(models),'uniqueModelTokens':len(model_counts),
            'brushModelReferences':len(brush),'uniqueBrushModelTokens':len(set(brush)),
            'namedModelReferences':len(named),'uniqueNamedModelTokens':len(named_counts),
            'scriptModels':len(script_models),'scriptBrushmodels':len(script_brush),
            'fxanimSceneEntities':len(fxanim),'destructibleScriptModels':len(destructible),
            'carScriptModels':len(car),'parkedDestructibleCars':len(parked_car),'animatedCarOverlays':len(animated_car),
        },
        'namedModelUseCounts':dict(sorted(named_counts.items(), key=lambda kv:(-kv[1],kv[0]))),
        'fxanimSceneEntities':[entity_record(e) for e in fxanim],
        'carEntities':[entity_record(e) for e in car],
        'displayGlassEntities':[entity_record(e) for e in display],
        'relevantEntities':[entity_record(e) for e in ents if relevant_entity(e)],
        'candidateGltfInventory':gltf,
        'policy':{
            'sourceTransformsOnly':True,
            'duplicatePhaseEntitiesMustNotBeRenderedSimultaneouslyWithoutRuntimeSemantics':True,
            'missingModelsMustNotBeFabricated':True,
            'purpose':'prevent static-only scene assembly from silently dropping MapEnt/dynamic/animated model classes'
        }
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    txt=json.dumps(out,indent=2,sort_keys=True)+'\n'; args.out.write_text(txt,encoding='utf-8')
    print(json.dumps({'out':str(args.out),'bytes':len(txt.encode()),'sha256':hashlib.sha256(txt.encode()).hexdigest(),'counts':out['counts'],'gltf':gltf and {k:gltf[k] for k in ('skins','animations','substringNamedMapEntModelTokenCount','namedMapEntModelTokenCount')}},indent=2))

if __name__=='__main__': main()
