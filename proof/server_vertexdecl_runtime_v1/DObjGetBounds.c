
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void __cdecl DObjGetBounds(DObj *param_1,vec3_t *param_2,vec3_t *param_3)

{
  code *pcVar1;
  bool bVar2;
  float fVar3;
  
  if (param_1 == (DObj *)0x0) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\xanim\\dobj.cpp",0x548,0,"(obj)","");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  fVar3 = (float)((uint)param_1->radius ^ ___mask__NegFloat_);
  (param_2->_s_0).x = fVar3;
  (param_2->_s_0).y = fVar3;
  (param_2->_s_0).z = fVar3;
  fVar3 = param_1->radius;
  (param_3->_s_0).x = fVar3;
  (param_3->_s_0).y = fVar3;
  (param_3->_s_0).z = fVar3;
  return;
}

