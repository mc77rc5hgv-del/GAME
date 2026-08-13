//! Bridge between the Yandex Games JS SDK (see `wasm_resources/index.html`)
//! and Jumpy's own session/asset systems. Deliberately does not build a new
//! pause/lifecycle system: it drives Jumpy's existing `game` session
//! activity flag (the same mechanism `ui::pause_menu` uses) and Jumpy's own
//! asset loading state, and only notifies JS of state changes it can't
//! observe on its own.

use crate::prelude::*;
use std::sync::atomic::{AtomicBool, Ordering};

/// Set by the JS side (via `jumpy_set_tab_hidden`, exported below) whenever
/// the browser tab is backgrounded/foregrounded. Read once per frame by
/// [`yandex_bridge_system`]. A plain atomic, not a bones resource, because
/// it's written from a raw JS callback with no `&mut Game` in scope.
static TAB_HIDDEN: AtomicBool = AtomicBool::new(false);

#[cfg(target_arch = "wasm32")]
mod js {
    use wasm_bindgen::prelude::*;

    #[wasm_bindgen]
    extern "C" {
        /// Called once, the first time the game has finished loading assets
        /// and is showing an interactive session (see [`super::yandex_bridge_system`]).
        #[wasm_bindgen(js_namespace = window, js_name = "__jumpyOnGameReady")]
        pub fn notify_game_ready();

        /// Called whenever the `game` match session's active state changes,
        /// so JS can call `GameplayAPI.start()` / `GameplayAPI.stop()`.
        #[wasm_bindgen(js_namespace = window, js_name = "__jumpyOnMatchActiveChanged")]
        pub fn notify_match_active_changed(active: bool);
    }

    /// Called from `wasm_resources/index.html` on `visibilitychange` / `blur` / `focus`.
    #[wasm_bindgen]
    pub fn jumpy_set_tab_hidden(hidden: bool) {
        super::TAB_HIDDEN.store(hidden, std::sync::atomic::Ordering::Relaxed);
    }
}

#[cfg(not(target_arch = "wasm32"))]
mod js {
    pub fn notify_game_ready() {}
    pub fn notify_match_active_changed(_active: bool) {}
}

#[derive(HasSchema, Clone, Copy, Debug, Default)]
#[repr(C)]
pub struct TabHidden(pub bool);

#[derive(HasSchema, Clone, Copy, Debug, Default)]
struct YandexBridgeState {
    ready_notified: bool,
    last_match_active: bool,
}

pub fn game_plugin(game: &mut Game) {
    game.init_shared_resource::<TabHidden>();
    game.init_shared_resource::<YandexBridgeState>();
    game.systems.add_before_system(yandex_bridge_system);
}

fn yandex_bridge_system(game: &mut Game) {
    // Mirror the JS-reported tab-visibility flag into a shared resource
    // (mute.rs also reads this to silence audio), and pause/resume the
    // match session exactly as `ui::pause_menu` does when the user presses
    // pause, so we're not inventing a second pause mechanism.
    let hidden = TAB_HIDDEN.load(Ordering::Relaxed);
    {
        let mut tab_hidden = game.shared_resource_mut::<TabHidden>();
        tab_hidden.0 = hidden;
    }
    {
        let mut sessions = game.shared_resource_mut::<Sessions>();
        if let Some(session) = sessions.get_mut(SessionNames::GAME) {
            // Same online/offline split `ui::pause_menu` uses: an online match
            // stays active (so it doesn't time out on other players) and only
            // has local input disabled, while an offline match's activity
            // flag is toggled directly.
            #[cfg(not(target_arch = "wasm32"))]
            let is_online = session
                .world
                .get_resource::<SyncingInfo>()
                .is_some_and(|x| x.is_online());
            #[cfg(target_arch = "wasm32")]
            let is_online = false;

            if is_online {
                session.runner.disable_local_input(hidden);
            } else {
                session.active = !hidden;
            }
        }
    }

    // Fire once, the moment asset loading finishes and the (already-running)
    // main menu session becomes the visible, interactive one - this is the
    // earliest point that satisfies LoadingAPI.ready()'s requirements.
    let assets_finished = game.shared_resource::<AssetServer>().load_progress.is_finished();
    if assets_finished {
        let mut state = game.shared_resource_mut::<YandexBridgeState>();
        if !state.ready_notified {
            state.ready_notified = true;
            drop(state);
            js::notify_game_ready();
        }
    }

    // Report match start/stop transitions so JS can call
    // GameplayAPI.start()/stop() only while an actual match is being played,
    // not while sitting in a menu.
    let match_active = {
        let sessions = game.shared_resource::<Sessions>();
        sessions
            .get(SessionNames::GAME)
            .map(|s| s.active)
            .unwrap_or(false)
    };
    let mut state = game.shared_resource_mut::<YandexBridgeState>();
    if match_active != state.last_match_active {
        state.last_match_active = match_active;
        drop(state);
        js::notify_match_active_changed(match_active);
    }
}
