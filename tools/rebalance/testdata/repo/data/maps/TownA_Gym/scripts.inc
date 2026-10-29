TownA_Gym_EventScript_Leader::
	trainerbattle_single TRAINER_LEADER_X, TownA_Gym_Text_LeaderIntro, TownA_Gym_Text_LeaderDefeat, TownA_Gym_EventScript_LeaderDefeated, NO_MUSIC
	end

TownA_Gym_EventScript_LeaderDefeated::
	giveitem ITEM_TM_SHADOW_BALL
	end

TownA_Gym_Pokemart:
	.2byte ITEM_TM_CHARM
	pokemartlistend
