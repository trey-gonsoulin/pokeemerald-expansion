"""Story routes per area (maps searched together) for classify.py.

Pair specs are 'Folder/kind:arg' ('|' joins alternatives) with kind conn:<dir>[:<MAP>] (leave by that
edge, optionally only the stretch joined to MAP), warp:<indices>, xy:x,y[;x,y], rect:x0,y0,x1,y1,
near:<trainer id or script label> (a tile next to it), deep:x,y (the dive patch nearest x,y).
Stage index: 0 Rival, 1 Roxanne, 2 Brawly, 3 Wattson, 4 Flannery, 5 Norman, 6 Winona, 7 Tate and Liza,
8 Juan, 9 Elite Four. It sets the HMs: Cut 2+, bike 3+, Rock Smash 4+, Strength 5+, Surf 6+, Waterfall 9.
"""

R111_SANDSTORM = [(11, 61), (12, 61), (13, 61), (14, 61), (12, 44), (13, 43), (14, 42), (16, 40), (17, 39), (18, 38)]

AREAS = {
    # --- Roxanne / Brawly ---------------------------------------------------------------
    'Route102': {'maps': ['Route102'], 'stage': 1, 'pairs': [('Route102/conn:right', 'Route102/conn:left')]},
    'Route104+PetalburgWoods': {
        'maps': ['Route104', 'PetalburgWoods'], 'stage': 1,
        'pairs': [('Route104/conn:right', 'Route104/conn:up'),     # Petalburg -> woods -> Rustboro
                  ('Route104/conn:up', 'Route104/warp:0')],         # Rustboro -> Briney's cottage (Brawly stage)
        # The Devon researcher scene (Aqua grunt battle) fires on these coord tiles.
        'script_tiles': {'TRAINER_GRUNT_PETALBURG_WOODS': {'PetalburgWoods': [(26, 23), (27, 23)]}},
    },
    'Route116': {'maps': ['Route116'], 'stage': 1, 'pairs': [('Route116/conn:left', 'Route116/warp:0')],
                 'note': 'Cut not assumed (the chase comes right after Roxanne)'},
    'RustboroGym': {'maps': ['RustboroCity_Gym'], 'stage': 1,
                    'pairs': [('RustboroCity_Gym/warp:0,1', 'RustboroCity_Gym/near:TRAINER_ROXANNE_1')]},
    'DewfordGym': {'maps': ['DewfordTown_Gym'], 'stage': 2,
                   'pairs': [('DewfordTown_Gym/warp:0,1', 'DewfordTown_Gym/near:TRAINER_BRAWLY_1')],
                   'note': 'darkness ignored'},
    # --- Wattson -------------------------------------------------------------------------
    'Route109': {'maps': ['Route109'], 'stage': 3,
                 'pairs': [('Route109/rect:19,21,23,23', 'Route109/conn:up')],
                 'note': "Briney's boat lands at the Route 109 dock below Slateport"},
    'Route110': {'maps': ['Route110'], 'stage': 3, 'abilities': {'bike': False},
                 'pairs': [('Route110/conn:down', 'Route110/conn:up')], 'note': 'no bike yet (Cycling Road closed)',
                 'script_tiles': {'TRAINER_MAY_ROUTE_110_MUDKIP': {'Route110': [(33, 56), (34, 56), (35, 56)]}}},
    'MauvilleGym': {'maps': ['MauvilleCity_Gym'], 'stage': 3,
                    'toggle': {'MauvilleCity_Gym': [(0, 15), (4, 12), (3, 9), (8, 9)]},
                    'pairs': [('MauvilleCity_Gym/warp:0,1', 'MauvilleCity_Gym/near:TRAINER_WATTSON_1')],
                    'note': 'beam barriers modelled in both switch states; any switch flips them'},
    # --- Flannery -------------------------------------------------------------------------
    'Route111': {'maps': ['Route111'], 'stage': 4, 'block': {'Route111': R111_SANDSTORM},
                 'pairs': [('Route111/conn:down', 'Route111/conn:left:ROUTE112'),
                           ('Route111/conn:left:ROUTE112', 'Route111/conn:left:ROUTE113')],
                 'note': 'desert sandstorm triggers treated as walls (no Go-Goggles)'},
    'Route112': {'maps': ['Route112'], 'stage': 4,
                 'pairs': [('Route112/conn:right', 'Route112/warp:4'),        # Route 111 -> Fiery Path
                           ('Route112/warp:5', 'Route112/conn:right'),        # Fiery Path north -> Route 111 north
                           ('Route112/conn:right', 'Route112/warp:0,1'),      # -> cable car
                           ('Route112/warp:2,3', 'Route112/conn:left')]},     # Jagged Pass foot -> Lavaridge
    'Route113': {'maps': ['Route113'], 'stage': 4, 'pairs': [('Route113/conn:right', 'Route113/conn:left')]},
    'Route114': {'maps': ['Route114'], 'stage': 4, 'pairs': [('Route114/conn:right', 'Route114/warp:0')]},
    'MtChimney': {'maps': ['MtChimney'], 'stage': 4,
                  'hide': ['TRAINER_SHELBY_1', 'TRAINER_MELISSA', 'TRAINER_SHEILA', 'TRAINER_SHIRLEY', 'TRAINER_SAWYER_1'],
                  'pairs': [('MtChimney/warp:0,1', 'MtChimney/near:TRAINER_MAXIE_MT_CHIMNEY'),
                            ('MtChimney/near:TRAINER_MAXIE_MT_CHIMNEY', 'MtChimney/warp:2,3')]},
    'JaggedPass': {'maps': ['JaggedPass'], 'stage': 4, 'pairs': [('JaggedPass/warp:2,3', 'JaggedPass/warp:0,1')]},
    'LavaridgeGym': {'maps': ['LavaridgeTown_Gym_1F', 'LavaridgeTown_Gym_B1F'], 'stage': 4,
                     'pairs': [('LavaridgeTown_Gym_1F/warp:0,1', 'LavaridgeTown_Gym_1F/near:TRAINER_FLANNERY_1')],
                     'note': 'buried trainers sit on the hole warps; holes/geysers modelled as plain warps'},
    # --- Norman ---------------------------------------------------------------------------
    'PetalburgGym': {'maps': ['PetalburgCity_Gym'], 'stage': 5,
                     'pairs': [('PetalburgCity_Gym/warp:0,1', 'PetalburgCity_Gym/near:PetalburgCity_Gym_EventScript_Norman')]},
    # --- Winona ---------------------------------------------------------------------------
    'Route118': {'maps': ['Route118'], 'stage': 6, 'pairs': [('Route118/conn:left', 'Route118/conn:up')]},
    'Route119': {'maps': ['Route119', 'Route119_WeatherInstitute_1F', 'Route119_WeatherInstitute_2F'], 'stage': 6,
                 'pairs': [('Route119/conn:down', 'Route119_WeatherInstitute_2F/near:TRAINER_SHELLY_WEATHER_INSTITUTE'),
                           ('Route119/warp:0', 'Route119/conn:right')],
                 'script_tiles': {'TRAINER_MAY_ROUTE_119_MUDKIP': {'Route119': [(25, 31), (26, 31)]}}},
    'Route120': {'maps': ['Route120'], 'stage': 6,
                 'pairs': [('Route120/conn:left', 'Route120/near:Route120_EventScript_Steven'),
                           ('Route120/conn:left', 'Route120/conn:right')],
                 'unblock': {'Route120': [(13, 15)]}},
    'FortreeGym': {'maps': ['FortreeCity_Gym'], 'stage': 6,
                   'pairs': [('FortreeCity_Gym/warp:0,1', 'FortreeCity_Gym/near:TRAINER_WINONA_1')],
                   'optimistic': 'rotating gates (src/rotating_gate.c) not modelled, so a skip here is unproven'},
    # --- Tate and Liza ---------------------------------------------------------------------
    'Route121': {'maps': ['Route121'], 'stage': 7,
                 'pairs': [('Route121/conn:left', 'Route121/conn:right'), ('Route121/conn:left|Route121/conn:right', 'Route121/conn:down')]},
    'MtPyre': {'maps': ['MtPyre_1F', 'MtPyre_Exterior', 'MtPyre_Summit'], 'stage': 7,
               'pairs': [('MtPyre_1F/warp:0,2', 'MtPyre_Summit/xy:22,9;23,9;24,9')]},
    'MagmaHideout': {'maps': ['MagmaHideout_1F', 'MagmaHideout_2F_1R', 'MagmaHideout_2F_2R', 'MagmaHideout_2F_3R',
                              'MagmaHideout_3F_1R', 'MagmaHideout_3F_2R', 'MagmaHideout_3F_3R', 'MagmaHideout_4F'],
                     'stage': 7, 'pairs': [('MagmaHideout_1F/warp:0', 'MagmaHideout_4F/near:TRAINER_MAXIE_MAGMA_HIDEOUT')]},
    'AquaHideout': {'maps': ['AquaHideout_1F', 'AquaHideout_B1F', 'AquaHideout_B2F'], 'stage': 7,
                    'pairs': [('AquaHideout_1F/warp:0,1', 'AquaHideout_B2F/near:TRAINER_MATT')]},
    'Route124': {'maps': ['Route124'], 'stage': 7, 'pairs': [('Route124/conn:left', 'Route124/conn:right:MOSSDEEP_CITY')],
                 'note': 'surface only (diving under it not needed)'},
    'MossdeepGym': {'maps': ['MossdeepCity_Gym'], 'stage': 7,
                    'pairs': [('MossdeepCity_Gym/warp:0,1', 'MossdeepCity_Gym/near:TRAINER_TATE_AND_LIZA_1')],
                    'optimistic': 'spin tiles and their switches not modelled (treated as plain floor), so a skip here is unproven'},
    # --- Juan -------------------------------------------------------------------------------
    'SpaceCenter': {'maps': ['MossdeepCity_SpaceCenter_1F'], 'stage': 8,
                    'unblock': {'MossdeepCity_SpaceCenter_1F': [(13, 2)]},
                    'pairs': [('MossdeepCity_SpaceCenter_1F/warp:0,1', 'MossdeepCity_SpaceCenter_1F/warp:2')]},
    'Route127': {'maps': ['Route127'], 'stage': 8, 'pairs': [('Route127/conn:up', 'Route127/conn:down')]},
    'Route128': {'maps': ['Route128'], 'stage': 8,
                 'pairs': [('Route128/conn:up', 'Route128/deep:38,26'), ('Route128/conn:up', 'Route128/conn:down'),
                           ('Route128/conn:up|Route128/conn:down', 'Route128/conn:right')]},
    'SeafloorCavern': {'maps': ['SeafloorCavern_Entrance'] + ['SeafloorCavern_Room%d' % i for i in range(1, 10)], 'stage': 8,
                       'pairs': [('SeafloorCavern_Entrance/warp:0', 'SeafloorCavern_Room9/xy:17,42')],
                       'note': 'assumes Strength boulders pushed out of the way (with them as walls there is no path at all)'},
    'Route126': {'maps': ['Route126'], 'stage': 8,
                 'pairs': [('Route126/conn:up|Route126/conn:right', 'Route126/deep:45,65')]},
    'Route129': {'maps': ['Route129'], 'stage': 8, 'pairs': [('Route129/conn:up', 'Route129/conn:left')]},
    'Route130': {'maps': ['Route130'], 'stage': 8, 'pairs': [('Route130/conn:right', 'Route130/conn:left')]},
    'Route131': {'maps': ['Route131'], 'stage': 8, 'pairs': [('Route131/conn:right', 'Route131/warp:0')]},
    'SootopolisGym': {'maps': ['SootopolisCity_Gym_1F'], 'stage': 8,
                      'pairs': [('SootopolisCity_Gym_1F/warp:0,1', 'SootopolisCity_Gym_1F/near:TRAINER_JUAN_1')]},
    # --- Elite Four -------------------------------------------------------------------------
    'VictoryRoad': {'maps': ['VictoryRoad_1F', 'VictoryRoad_B1F', 'VictoryRoad_B2F'], 'stage': 9,
                    'pairs': [('VictoryRoad_1F/warp:0', 'VictoryRoad_1F/warp:1')],
                    'script_tiles': {'TRAINER_WALLY_VR_1': {'VictoryRoad_1F': [(2, 23), (3, 23)]}},
                    'note': 'assumes Strength boulders pushed out of the way (with them as walls there is no path at all)'},
}

HIDDEN_CHIMNEY = 'Mt. Chimney rim trainer: hidden (FLAG_HIDE_MT_CHIMNEY_TRAINERS) until you reach Lavaridge, so absent during the story climb; optional afterwards'
PETALBURG = ('UNCERTAIN', 'Petalburg Gym: each room\'s doors open only after its trainer; every route is lobby -> {RANDALL|MARY} -> {PARKER|ALEXIA|GEORGE} -> {JODY|BERKE} -> Norman, so exactly one trainer per tier (3 battles) is forced, the player picks which')
WINSTRATE = ('AVOIDABLE', 'Winstrate family: Victor asks YES/NO outside their Route 111 house; the four battles only on YES')

# Choose-one groups: the player must fight exactly one trainer of each group, and picks which.
# classify.py attaches each as one_of, and fails if the grid finds a group that isn't listed here.
# Petalburg Gym is one trainer per room; the other two come from the grid search.
CHOOSE_ONE = (
    ('TRAINER_RANDALL', 'TRAINER_MARY'),
    ('TRAINER_PARKER', 'TRAINER_ALEXIA', 'TRAINER_GEORGE'),
    ('TRAINER_JODY', 'TRAINER_BERKE'),
    ('TRAINER_GRUNT_WEATHER_INST_1', 'TRAINER_GRUNT_WEATHER_INST_4'),
    ('TRAINER_SAMUEL', 'TRAINER_SHANNON'),
)

MANUAL = {
    'TRAINER_SHELBY_1': ('AVOIDABLE', HIDDEN_CHIMNEY),
    'TRAINER_MELISSA': ('AVOIDABLE', HIDDEN_CHIMNEY),
    'TRAINER_SHEILA': ('AVOIDABLE', HIDDEN_CHIMNEY),
    'TRAINER_SHIRLEY': ('AVOIDABLE', HIDDEN_CHIMNEY),
    'TRAINER_SAWYER_1': ('AVOIDABLE', HIDDEN_CHIMNEY),
    'TRAINER_RANDALL': PETALBURG, 'TRAINER_MARY': PETALBURG, 'TRAINER_PARKER': PETALBURG, 'TRAINER_ALEXIA': PETALBURG,
    'TRAINER_GEORGE': PETALBURG, 'TRAINER_JODY': PETALBURG, 'TRAINER_BERKE': PETALBURG,
    'TRAINER_VICTOR': WINSTRATE, 'TRAINER_VICTORIA': WINSTRATE, 'TRAINER_VIVI': WINSTRATE, 'TRAINER_VICKY': WINSTRATE,
    'TRAINER_GRUNT_RUSTURF_TUNNEL': ('FORCED', 'scripted: the Devon Goods thief, fought to recover the goods (needed for the Stone letter / Briney)'),
    'TRAINER_MIKE_2': ('AVOIDABLE', 'Rusturf Tunnel east side, behind the rocks until Rock Smash; never on the story path'),
    'TRAINER_GRUNT_MUSEUM_1': ('FORCED', 'scripted: Oceanic Museum 2F, fought in sequence when delivering the Devon Goods to Stern'),
    'TRAINER_GRUNT_MUSEUM_2': ('FORCED', 'scripted: Oceanic Museum 2F, second grunt of the same delivery scene'),
    'TRAINER_GRUNT_JAGGED_PASS': ('AVOIDABLE', 'guards the closed Magma Hideout door until Mt. Pyre, then hidden (FLAG_HIDE_JAGGED_PASS_MAGMA_GUARD) before the hideout is needed'),
    'TRAINER_GRUNT_SPACE_CENTER_2': ('FORCED', 'scripted stair guard on Space Center 1F (talk battle; moves off the stairs only once beaten)'),
    'TRAINER_GRUNT_SPACE_CENTER_5': ('FORCED', 'scripted: Space Center 2F three-grunt gauntlet; declining sends you back downstairs'),
    'TRAINER_GRUNT_SPACE_CENTER_6': ('FORCED', 'scripted: Space Center 2F three-grunt gauntlet'),
    'TRAINER_GRUNT_SPACE_CENTER_7': ('FORCED', 'scripted: Space Center 2F three-grunt gauntlet'),
}

OPTIONAL_MAPS = {
    'Route109_SeashoreHouse': 'optional side house (Seashore House challenge)',
    'Route110_TrickHousePuzzle1': 'Trick House is optional',
    'Route110_TrickHousePuzzle2': 'Trick House is optional',
    'Route110_TrickHousePuzzle3': 'Trick House is optional',
    'Route110_TrickHousePuzzle4': 'Trick House is optional',
    'Route110_TrickHousePuzzle6': 'Trick House is optional',
    'Route110_TrickHousePuzzle7': 'Trick House is optional',
    'Route103': 'Route 103 east (land and water) is off the story path after the first rival fight',
    'Route117': 'Route 117 / Verdanturf are not on the story path (Mauville -> Route 111 north)',
    'Route115': 'Route 115 (Rustboro north) is not on the story path',
    'Route105': 'Routes 105-108 (sea between Petalburg, Dewford and Slateport) are optional once Surf is out',
    'Route106': 'Routes 105-108 are optional (Briney ferries the story legs)',
    'Route107': 'Routes 105-108 are optional (Briney ferries the story legs)',
    'Route108': 'Routes 105-108 are optional; the Abandoned Ship is a side area',
    'AbandonedShip_Corridors_1F': 'Abandoned Ship is optional',
    'AbandonedShip_Corridors_B1F': 'Abandoned Ship is optional',
    'AbandonedShip_Rooms_1F': 'Abandoned Ship is optional',
    'AbandonedShip_Rooms2_1F': 'Abandoned Ship is optional',
    'Route123': 'Route 123 (Route 118 east to Mt. Pyre) is an alternative way round; Route 121 -> 122 is the story path',
    'Route125': 'Route 125 (north of Mossdeep, Shoal Cave) is optional',
    'MtPyre_2F': 'Mt. Pyre interior floors are optional; the story climbs the exterior to the summit',
    'MtPyre_3F': 'Mt. Pyre interior floors are optional',
    'MtPyre_4F': 'Mt. Pyre interior floors are optional',
    'MtPyre_5F': 'Mt. Pyre interior floors are optional',
    'MtPyre_6F': 'Mt. Pyre interior floors are optional',
    'Route132': 'Routes 132-134 (Pacifidlog to Slateport) are optional',
    'Route133': 'Routes 132-134 are optional',
    'Route134': 'Routes 132-134 are optional',
    'SootopolisCity_Gym_B1F': "Sootopolis Gym B1F is a dead-end trainer room off the 1F stairs; Juan's ice path skips it",
    'MeteorFalls_1F_2R': 'Meteor Falls inner room (Waterfall) is optional',
}

BOSS_NOTES = {
    'TRAINER_MAY_RUSTBORO_MUDKIP': {'required': False, 'reason': 'optional: May asks YES/NO in Rustboro / outside Briney\'s cottage (FLAG_DEFEATED_RIVAL_RUSTBORO only on YES)'},
    'TRAINER_MAY_LILYCOVE_MUDKIP': {'required': False, 'reason': 'optional: talk-to rival in Lilycove asks YES/NO'},
    'TRAINER_MAY_ROUTE_103_MUDKIP': {'required': True, 'reason': 'scripted first rival battle (Birch errand)'},
    'TRAINER_MAY_ROUTE_110_MUDKIP': {'required': True, 'reason': 'coord trigger across Route 110 (y=56)'},
    'TRAINER_MAY_ROUTE_119_MUDKIP': {'required': True, 'reason': 'coord trigger on Route 119 (25-26, 31)'},
    'TRAINER_WALLY_MAUVILLE': {'required': True, 'reason': 'scripted outside Mauville Gym'},
    'TRAINER_WALLY_VR_1': {'required': True, 'reason': 'coord trigger in Victory Road 1F (2-3, 23)'},
}
