# Map JSON data

# Inputs
MAPS_DIR = $(DATA_ASM_SUBDIR)/maps
LAYOUTS_DIR = $(DATA_ASM_SUBDIR)/layouts

# Outputs
MAPS_OUTDIR := $(MAPS_DIR)
LAYOUTS_OUTDIR := $(LAYOUTS_DIR)
INCLUDECONSTS_OUTDIR := include/constants

AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/map_groups.h
AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/layouts.h
AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/map_event_ids.h
AUTO_GEN_TARGETS += $(DATA_SRC_SUBDIR)/map_group_count.h
AUTO_GEN_TARGETS += $(DATA_SRC_SUBDIR)/debug_map_names.h

MAP_DIRS := $(dir $(wildcard $(MAPS_DIR)/*/map.json))
MAP_CONNECTIONS := $(patsubst $(MAPS_DIR)/%/,$(MAPS_DIR)/%/connections.inc,$(MAP_DIRS))
MAP_EVENTS := $(patsubst $(MAPS_DIR)/%/,$(MAPS_DIR)/%/events.inc,$(MAP_DIRS))
MAP_HEADERS := $(patsubst $(MAPS_DIR)/%/,$(MAPS_DIR)/%/header.inc,$(MAP_DIRS))
MAP_JSONS := $(patsubst $(MAPS_DIR)/%/,$(MAPS_DIR)/%/map.json,$(MAP_DIRS))

$(DATA_ASM_BUILDDIR)/maps.o: $(DATA_ASM_SUBDIR)/maps.s $(LAYOUTS_DIR)/layouts.inc $(LAYOUTS_DIR)/layouts_table.inc $(MAPS_DIR)/headers.inc $(MAPS_DIR)/groups.inc $(MAPS_DIR)/connections.inc $(MAP_CONNECTIONS) $(MAP_HEADERS)
	$(PREPROC) -s $< charmap.txt | $(CPP) $(CPPFLAGS) -I include - | $(PREPROC) -ie $< charmap.txt | $(AS) $(ASFLAGS) -o $@
$(DATA_ASM_BUILDDIR)/map_events.o: $(DATA_ASM_SUBDIR)/map_events.s $(MAPS_DIR)/events.inc $(MAP_EVENTS)
	$(PREPROC) -s $< charmap.txt | $(CPP) $(CPPFLAGS) -I include - | $(PREPROC) -ie $< charmap.txt | $(AS) $(ASFLAGS) -o $@

$(MAPS_OUTDIR)/%/header.inc $(MAPS_OUTDIR)/%/events.inc $(MAPS_OUTDIR)/%/connections.inc: $(MAPS_DIR)/%/map.json $(INCLUDECONSTS_OUTDIR)/map_groups.h $(MAPJSON)
	$(MAPJSON) map emerald $< $(LAYOUTS_DIR)/layouts.json $(@D)


# mapjson groups and mapjson layouts each write several files. Listing them all as targets of one
# rule makes -j run the recipe once per target, concurrently (make 3.81 has no grouped targets), so
# the outputs depend on a stamp with an empty recipe instead. The stamp is touched before mapjson
# runs and moved into place after, so a failed run leaves it out of date. mapjson rewrites every
# output, so none is older than the stamp. A missing output (checked when make starts) forces the
# stamp to rebuild; clean-generated removes the stamps with the other AUTO_GEN_TARGETS.
MAPJSON_GROUPS_STAMP := .mapjson_groups.stamp
MAPJSON_GROUPS_OUTPUTS := $(MAPS_OUTDIR)/connections.inc $(MAPS_OUTDIR)/groups.inc $(MAPS_OUTDIR)/events.inc $(MAPS_OUTDIR)/headers.inc $(INCLUDECONSTS_OUTDIR)/map_groups.h $(DATA_SRC_SUBDIR)/map_group_count.h $(DATA_SRC_SUBDIR)/debug_map_names.h
MAPJSON_LAYOUTS_STAMP := .mapjson_layouts.stamp
MAPJSON_LAYOUTS_OUTPUTS := $(LAYOUTS_OUTDIR)/layouts.inc $(LAYOUTS_OUTDIR)/layouts_table.inc $(INCLUDECONSTS_OUTDIR)/layouts.h
AUTO_GEN_TARGETS += $(MAPJSON_GROUPS_STAMP) $(MAPJSON_LAYOUTS_STAMP)
force_if_missing = $(if $(filter-out $(wildcard $1),$1),FORCE)

# mapjson groups also rewrites the tracked heal_locations.json, which jsonproc reads: as a stamp
# output, jsonproc runs after it and sees its new contents.
$(MAPJSON_GROUPS_OUTPUTS) $(DATA_SRC_SUBDIR)/heal_locations.json: $(MAPJSON_GROUPS_STAMP) ;
$(MAPJSON_GROUPS_STAMP): $(MAPS_DIR)/map_groups.json $(MAP_JSONS) .map_version $(MAPJSON) $(call force_if_missing,$(MAPJSON_GROUPS_OUTPUTS))
	@touch $@.tmp
	@$(MAPJSON) groups $(MAP_VERSION) $(filter %.json,$^) $(MAPS_OUTDIR) $(INCLUDECONSTS_OUTDIR)
	@echo "$(MAPJSON) groups $(MAP_VERSION) $(MAPS_DIR)/map_groups.json <MAP_JSONS> $(MAPS_OUTDIR) $(INCLUDECONSTS_OUTDIR)"
	@mv $@.tmp $@

$(MAPJSON_LAYOUTS_OUTPUTS): $(MAPJSON_LAYOUTS_STAMP) ;
$(MAPJSON_LAYOUTS_STAMP): $(LAYOUTS_DIR)/layouts.json .map_version $(MAPJSON) $(call force_if_missing,$(MAPJSON_LAYOUTS_OUTPUTS))
	@touch $@.tmp
	$(MAPJSON) layouts $(MAP_VERSION) $< $(LAYOUTS_OUTDIR) $(INCLUDECONSTS_OUTDIR)
	@mv $@.tmp $@

# Generate constants for map events, which depend on data that's distributed across the map.json files.
# There's a lot of map.json files, so we print an abbreviated output with echo.
$(INCLUDECONSTS_OUTDIR)/map_event_ids.h: $(MAP_JSONS) $(MAPJSON)
	@$(MAPJSON) event_constants emerald $(MAP_JSONS) $(INCLUDECONSTS_OUTDIR)/map_event_ids.h
	@echo "$(MAPJSON) event_constants emerald <MAP_JSONS> $(INCLUDECONSTS_OUTDIR)/map_event_ids.h"

.map_version : FORCE
	@(echo "$(MAP_VERSION)" | cmp $@ -) || echo "$(MAP_VERSION)" > .map_version

FORCE:
.PHONY : FORCE
