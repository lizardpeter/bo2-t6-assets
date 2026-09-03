#!/usr/bin/env python3
import argparse,json,subprocess,sys
from pathlib import Path
EXP={'shaderCount':73,'layerStepCount':82,'xyzwRecurrenceCheckCount':328,'recurrenceFailureCount':0,'operatorStepCounts':{'b':74,'t':8},'baselineChannelShaderCounts':{'w:color_alpha':38,'w:default_0':7,'w:explicit_spec':28,'x:default_0.2':45,'x:explicit_spec':28,'y:default_0.2':45,'y:explicit_spec':28,'z:default_0.2':45,'z:explicit_spec':28},'sameRgbWeightDagMismatchCount':0,'rowsSha256':'b24316e179e43b24ec1e65998517497820bb20cf472cd960b529b4725b64cf45'}
def check(d):assert d['format']=='t6-retail-layered-specular-compositor-v1' and d['sourceSlot4ShaderSetSha256']=='f3065ec05f2992048ceb7e3fae845f13e6e8b57f1eb717e644b26cb45774f799' and d['summary']==EXP and len(d['examples'])==4
def main():
 a=argparse.ArgumentParser();a.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LAYERED_SPECULAR_COMPOSITOR_V1.json'));a.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_layered_specular_compositor_v1.py'));a.add_argument('--rerun',action='store_true');a.add_argument('--out',type=Path,default=Path('/tmp/t6_spec_proof.json'));x=a.parse_args();check(json.loads(x.manifest.read_text()))
 if x.rerun:
  subprocess.check_call([sys.executable,str(x.verifier),'--out',str(x.out)]);check(json.loads(x.out.read_text()));assert json.loads(x.out.read_text())==json.loads(x.manifest.read_text())
 print('PASS: T6 retained layered specular compositor regression')
if __name__=='__main__':main()
