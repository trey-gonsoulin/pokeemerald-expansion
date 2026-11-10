#ifndef GUARD_CONFIG_DEBUG_H
#define GUARD_CONFIG_DEBUG_H

// Overworld Debug
#define DEBUG_OVERWORLD_MENU            DISABLED_ON_RELEASE // Enables an overworld debug menu to change flags, variables, giving Pokémon and more, accessed by holding R and pressing START while in the overworld by default.
#define DEBUG_OVERWORLD_HELD_KEYS       (R_BUTTON)          // The keys required to be held to open the debug menu.
#define DEBUG_OVERWORLD_TRIGGER_EVENT   pressedStartButton  // The event that opens the menu when holding the key(s) defined in DEBUG_OVERWORLD_HELD_KEYS.
#define DEBUG_OVERWORLD_IN_MENU         FALSE               // Replaces the overworld debug menu button combination with a start menu entry (above Pokédex).
#define DEBUG_FLAG_VAR_NAMES            TRUE                // Shows flag and var constant names in the overworld debug menu's Set Flag and Set Var, with Start for A-Z order. The name tables cost about 50 KB of ROM when the debug menu is on (none in release builds).
// Debug Warp favourites, listed in Utilities > Recent warps… after "Back to <map>" and before this session's warps.
// Up to 11 DEBUG_WARP_FAVOURITE(map, warp id) entries, one after another; warp 0 of a map without warps is its middle.
// Leave it empty for none. The warp ids below are the Pokémon Center doors, May's house in Littleroot and the Battle Pike in the Frontier.
#define DEBUG_WARP_FAVOURITES                               \
    DEBUG_WARP_FAVOURITE(MAP_LITTLEROOT_TOWN, 0)            \
    DEBUG_WARP_FAVOURITE(MAP_RUSTBORO_CITY, 3)              \
    DEBUG_WARP_FAVOURITE(MAP_SLATEPORT_CITY, 0)             \
    DEBUG_WARP_FAVOURITE(MAP_LILYCOVE_CITY, 2)              \
    DEBUG_WARP_FAVOURITE(MAP_EVER_GRANDE_CITY, 1)           \
    DEBUG_WARP_FAVOURITE(MAP_BATTLE_FRONTIER_OUTSIDE_WEST, 0)

// Battle Debug Menu
#define DEBUG_BATTLE_MENU               DISABLED_ON_RELEASE // If set to TRUE, enables a debug menu to use in battles by pressing the Select button.
#define DEBUG_AI_DELAY_TIMER            FALSE // If set to TRUE, displays the number of frames it takes for the AI to choose a move. Replaces the "What will PKMN do" text. Useful for devs or anyone who modifies the AI code and wants to see if it doesn't take too long to run.

// Pokémon Debug
#define DEBUG_POKEMON_SPRITE_VISUALIZER DISABLED_ON_RELEASE // Enables a debug menu for Pokémon sprites and icons, accessed by pressing Select in the summary screen.

#endif // GUARD_CONFIG_DEBUG_H
