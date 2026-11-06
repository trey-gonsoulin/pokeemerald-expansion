#ifndef GUARD_BATTLE_DOME_H
#define GUARD_BATTLE_DOME_H

#include "constants/battle_dome.h"

int GetDomeTrainerSelectedMons(u16 tournamentTrainerId);
int TrainerIdToDomeTournamentId(u16 trainerId);

#if TESTING
u16 Test_GetWinningMove(int winnerTournamentId, int loserTournamentId, u8 roundId);
#endif

#endif // GUARD_BATTLE_DOME_H
