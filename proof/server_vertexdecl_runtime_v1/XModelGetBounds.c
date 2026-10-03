
void __cdecl XModelGetBounds(XModel *param_1,vec3_t *param_2,vec3_t *param_3)

{
  (param_2->_s_0).x = (param_1->mins)._s_0.x;
  (param_2->_s_0).y = (param_1->mins)._s_0.y;
  (param_2->_s_0).z = (param_1->mins)._s_0.z;
  (param_3->_s_0).x = (param_1->maxs)._s_0.x;
  (param_3->_s_0).y = (param_1->maxs)._s_0.y;
  (param_3->_s_0).z = (param_1->maxs)._s_0.z;
  return;
}

