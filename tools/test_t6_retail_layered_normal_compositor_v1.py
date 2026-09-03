#!/usr/bin/env python3
import argparse,importlib.util,json
from pathlib import Path
EXP={'shaderCount':107,'layerStepCount':129,'xyRecurrenceCheckCount':258,'recurrenceFailureCount':0,'operatorStepCounts':{'b':110,'t':19},'baselineShaderCounts':{'explicit_normal':98,'zero':9},'transformStepCounts':{'direct':9,'transform2x2':120},'uniqueTransformDagPairCount':69,'sameRgbWeightDagMismatchCount':0,'rowsSha256':'89c415c4233ff11fed4f72862bfdcb6dacde95f421373822c151564069bde05f','transformDagSetSha256':'9194f67aa2f3198511607d5d8f10ad0ae230008ef06cbe98ac7ebcf9ce246e7e'}
def load(p):s=importlib.util.spec_from_file_location('v',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def check(d):assert d['format']=='t6-retail-layered-normal-compositor-v1' and d['sourceSlot4ShaderSetSha256']=='f3065ec05f2992048ceb7e3fae845f13e6e8b57f1eb717e644b26cb45774f799' and d['summary']==EXP and len(d['examples'])==4
def main():
 a=argparse.ArgumentParser();a.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_LAYERED_NORMAL_COMPOSITOR_V1.json'));a.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_layered_normal_compositor_v1.py'));a.add_argument('--rerun',action='store_true');a.add_argument('--out',type=Path,default=Path('/tmp/t6_normal_proof.json'));x=a.parse_args();check(json.loads(x.manifest.read_text()))
 if x.rerun:
  import subprocess,sys;subprocess.check_call([sys.executable,str(x.verifier),'--out',str(x.out)]);check(json.loads(x.out.read_text()));assert json.loads(x.out.read_text())==json.loads(x.manifest.read_text())
 print('PASS: T6 retained layered normal compositor regression')
if __name__=='__main__':main()
