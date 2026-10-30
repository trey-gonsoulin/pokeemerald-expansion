// The fork's exp formula options (#154), used by ApplyExperienceMultipliers
// (src/battle_script_commands.c). tools/rebalance models the same math
// (scaling_factors, Overlevel.apply) and its tests read these tables.
#include "global.h"
#include "config_changes.h"
#include "exp_formula.h"

// The test override stores these configs in 8 bits (config_changes.h).
STATIC_ASSERT(B_EXP_OVERLEVEL_CUTOFF <= 255 && B_EXP_OVERLEVEL_HALVING <= 255, ExpOverlevelConfigsFitIn8Bits);

// (i^3.5)/4: the level scaling with B_SCALED_EXP_STEEP, in place of
// sExperienceScalingFactors' (i^2.5)/4.
const s32 gExperienceScalingFactorsSteep[] =
{
    0, 0, 2, 11, 32, 69, 132, 226,
    362, 546, 790, 1103, 1496, 1980, 2566, 3267,
    4096, 5064, 6185, 7474, 8944, 10609, 12485, 14587,
    16930, 19531, 22405, 25568, 29039, 32834, 36971, 41467,
    46340, 51610, 57294, 63412, 69984, 77027, 84563, 92611,
    101192, 110327, 120036, 130340, 141261, 152821, 165041, 177943,
    191550, 205885, 220970, 236829, 253484, 270960, 289279, 308467,
    328547, 349544, 371482, 394386, 418282, 443194, 469149, 496171,
    524288, 553524, 583907, 615462, 648218, 682200, 717435, 753952,
    791778, 830940, 871467, 913386, 956726, 1001515, 1047782, 1095556,
    1144866, 1195742, 1248212, 1302306, 1358055, 1415488, 1474635, 1535526,
    1598193, 1662666, 1728975, 1797152, 1867228, 1939234, 2013202, 2089164,
    2167151, 2247196, 2329331, 2413588, 2500000, 2588599, 2679418, 2772491,
    2867851, 2965531, 3065565, 3167985, 3272827, 3380124, 3489911, 3602221,
    3717090, 3834551, 3954640, 4077391, 4202841, 4331023, 4461973, 4595728,
    4732322, 4871792, 5014174, 5159503, 5307816, 5459150, 5613541, 5771026,
    5931641, 6095425, 6262413, 6432644, 6606155, 6782983, 6963166, 7146743,
    7333751, 7524228, 7718213, 7915745, 8116861, 8321601, 8530003, 8742107,
    8957952, 9177576, 9401020, 9628323, 9859525, 10094665, 10333784, 10576922,
    10824119, 11075415, 11330851, 11590467, 11854305, 12122405, 12394808, 12671555,
    12952689, 13238249, 13528279, 13822819, 14121911, 14425597, 14733920, 15046921,
    15364643, 15687129, 16014420, 16346560, 16683592, 17025558, 17372502, 17724466,
    18081495, 18443631, 18810919, 19183401, 19561122, 19944126, 20332457, 20726158,
    21125275, 21529852, 21939933, 22355564, 22776788, 23203650, 23636197, 24074473,
    24518523, 24968392, 25424127, 25885773, 26353376, 26826980, 27306634, 27792382,
    28284271, 28782347, 29286657, 29797247, 30314163, 30837454, 31367165, 31903344,
    32446038, 32995294, 33551160,
};

// 4096 * 2^(-k/16): the over-level penalty's fraction of a halving, in 16ths.
static const u16 sExpHalvingFractions[16] =
{
    4096, 3922, 3756, 3597, 3444, 3298, 3158, 3025, 2896, 2774, 2656, 2543, 2435, 2332, 2233, 2139,
};

// Past B_EXP_OVERLEVEL_CUTOFF percent above the fainted Pokémon's level, the
// exp halves every B_EXP_OVERLEVEL_HALVING percent of its level further (the
// whole halvings as a shift, the rest in 16ths), at least 1. Halving 0 gives
// 1 exp straight past the cutoff. No exp stays no exp.
s32 ApplyOverlevelPenalty(s32 exp, u32 faintedLevel, u32 expGetterLevel)
{
    s32 over = (s32)(expGetterLevel * 100) - (s32)(faintedLevel * (100 + GetConfig(B_EXP_OVERLEVEL_CUTOFF)));
    s32 span = faintedLevel * GetConfig(B_EXP_OVERLEVEL_HALVING);
    s32 halvings;

    if (exp <= 0 || over <= 0)
        return exp;
    if (span == 0)
        return 1;
    halvings = over / span;
    if (halvings >= 32)
        return 1;
    exp = ((u64)exp * sExpHalvingFractions[(over % span) * 16 / span]) >> (12 + halvings);
    return exp > 0 ? exp : 1;
}
