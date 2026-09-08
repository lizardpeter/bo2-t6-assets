#!/usr/bin/env python3
import importlib.util
import tempfile
from pathlib import Path

MOD_PATH = Path(__file__).with_name('t6_mp7_r2_xanim_notetrack_v1.py')
spec = importlib.util.spec_from_file_location('m', MOD_PATH)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def weapon_text(overrides=None):
    fields = [
        ('idleAnim','viewmodel_mp7_idle'),
        ('fireAnim','viewmodel_mp7_fire'),
        ('lastShotAnim','viewmodel_mp7_fire'),
        ('reloadAnim','viewmodel_mp7_reload'),
        ('reloadEmptyAnim','viewmodel_mp7_reload_empty'),
        ('raiseAnim','viewmodel_mp7_pullout'),
        ('dropAnim','viewmodel_mp7_putaway'),
        ('firstRaiseAnim','viewmodel_mp7_first_raise'),
        ('altRaiseAnim','viewmodel_mp7_pullout'),
        ('altDropAnim','viewmodel_mp7_putaway'),
        ('quickRaiseAnim','viewmodel_mp7_pullout_quick'),
        ('quickDropAnim','viewmodel_mp7_putaway'),
        ('emptyRaiseAnim','viewmodel_mp7_pullout'),
        ('emptyDropAnim','viewmodel_mp7_putaway'),
        ('sprintInAnim','viewmodel_mp7_sprint_in'),
        ('sprintLoopAnim','viewmodel_mp7_sprint_loop'),
        ('sprintOutAnim','viewmodel_mp7_sprint_out'),
        ('crawlInAnim','viewmodel_mp7_crawl_in'),
        ('crawlForwardAnim','viewmodel_mp7_crawl_forward'),
        ('crawlBackAnim','viewmodel_mp7_crawl_back'),
        ('crawlRightAnim','viewmodel_mp7_crawl_right'),
        ('crawlLeftAnim','viewmodel_mp7_crawl_left'),
        ('crawlOutAnim','viewmodel_mp7_crawl_out'),
        ('crawlEmptyInAnim','viewmodel_mp7_crawl_in'),
        ('crawlEmptyForwardAnim','viewmodel_mp7_crawl_forward'),
        ('crawlEmptyBackAnim','viewmodel_mp7_crawl_back'),
        ('crawlEmptyRightAnim','viewmodel_mp7_crawl_right'),
        ('crawlEmptyLeftAnim','viewmodel_mp7_crawl_left'),
        ('crawlEmptyOutAnim','viewmodel_mp7_crawl_out'),
        ('adsFireAnim','viewmodel_mp7_ads_fire'),
        ('adsLastShotAnim','viewmodel_mp7_ads_fire'),
        ('adsUpAnim','viewmodel_mp7_ads_up'),
        ('adsDownAnim','viewmodel_mp7_ads_down'),
        ('dtp_in','viewmodel_mp7_d2p_in'),
        ('dtp_loop','viewmodel_mp7_d2p_loop'),
        ('dtp_out','viewmodel_mp7_d2p_out'),
        ('playerAnimType','handleclip'),
        ('animHorRotateInc','0'),
    ]
    if overrides:
        fields = [(k, overrides.get(k,v)) for k,v in fields]
    return 'WEAPONFILE\\' + '\\'.join(x for kv in fields for x in kv)


def main():
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); a=td/'a'; b=td/'b'
        a.write_text(weapon_text()); b.write_text(weapon_text())
        closed=m.close_weapon_membership({'common_mp':a,'common_patch_mp':b})
        assert closed['animationUseCountPerCopy']==36
        assert closed['uniqueTargetCount']==23
        assert closed['targetNamesInFirstUseOrder'][0]=='viewmodel_mp7_idle'
        assert closed['targetNamesInFirstUseOrder'][-1]=='viewmodel_mp7_d2p_out'
        assert not m.is_xanim_reference_field('playerAnimType')
        assert not m.is_xanim_reference_field('animHorRotateInc')
        assert m.is_xanim_reference_field('dtp_in')
        b.write_text(weapon_text({'fireAnim':'viewmodel_other_fire'}))
        try:
            m.close_weapon_membership({'common_mp':a,'common_patch_mp':b})
        except ValueError as e:
            assert 'diverge' in str(e)
        else:
            raise AssertionError('divergent animation reference must fail closed')
    print('ok')

if __name__=='__main__': main()
