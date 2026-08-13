use crate::prelude::*;

/// Global mute toggle (`M` key), independent of the per-player control
/// scheme since it isn't a gameplay action for either player.
pub fn game_plugin(game: &mut Game) {
    game.init_shared_resource::<Muted>();
    game.systems.add_before_system(update_mute);
}

#[derive(HasSchema, Clone, Copy, Debug, Default)]
#[repr(C)]
pub struct Muted(pub bool);

fn update_mute(game: &mut Game) {
    let keyboard = game.shared_resource::<KeyboardInputs>();
    let m_pressed = keyboard
        .key_events
        .iter()
        .any(|x| x.key_code == Set(KeyCode::M) && x.button_state.pressed());
    drop(keyboard);

    if m_pressed {
        let mut muted = game.shared_resource_mut::<Muted>();
        muted.0 = !muted.0;
    }

    let muted = game.shared_resource::<Muted>().0;
    let base_volume = {
        let storage = game.shared_resource::<Storage>();
        storage
            .get::<Settings>()
            .map(|s| s.main_volume)
            .unwrap_or(1.0)
    };
    let mut audio_center = game.shared_resource_mut::<AudioCenter>();
    audio_center.set_main_volume_scale(if muted { 0.0 } else { base_volume });
}
