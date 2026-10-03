
void __cdecl CG_GetPoseAbsMinMax(cpose_t *param_1,vec3_t *param_2,vec3_t *param_3)

{
  code *pcVar1;
  bool bVar2;
  
  if (param_1 == (cpose_t *)0x0) {
    bVar2 = Assert_MyHandler("c:\\t6\\code\\src\\cgame_mp\\cg_ents_mp.cpp",0x1590,0,"(pose)","");
    if (!bVar2) {
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
  }
  (param_2->_s_0).x = (param_1->absmin)._s_0.x;
  (param_2->_s_0).y = (param_1->absmin)._s_0.y;
  (param_2->_s_0).z = (param_1->absmin)._s_0.z;
  (param_3->_s_0).x = (param_1->absmax)._s_0.x;
  (param_3->_s_0).y = (param_1->absmax)._s_0.y;
  (param_3->_s_0).z = (param_1->absmax)._s_0.z;
  return;
}

