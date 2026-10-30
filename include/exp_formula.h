#ifndef GUARD_EXP_FORMULA_H
#define GUARD_EXP_FORMULA_H

// The fork's exp formula options (#154), used by ApplyExperienceMultipliers.
extern const s32 gExperienceScalingFactorsSteep[];

s32 ApplyOverlevelPenalty(s32 exp, u32 faintedLevel, u32 expGetterLevel);

#endif // GUARD_EXP_FORMULA_H
