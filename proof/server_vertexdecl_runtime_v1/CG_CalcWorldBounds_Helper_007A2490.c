
int __cdecl DObjHasCollmap(DObj *param_1)

{
  int iVar1;
  
  if (param_1->numModels != '\0') {
    iVar1 = XModelHasCollmap(*(param_1->field15_0x78).localModels);
    return iVar1;
  }
  return 0;
}

