// The rebalance model in Pyodide (#151): the tool's own modules and its
// curve_data.json snapshot, run through rebalance.explore_run.
// Shared by worker.js and by anything that drives the model outside a page.

export const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';

// Pyodide path -> path relative to this directory. rebalance imports
// gamedata, which imports area_archetypes' restock (and its imports).
export const FILES = {
    '/tools/rebalance/rebalance.py': '../rebalance.py',
    '/tools/rebalance/gamedata.py': '../gamedata.py',
    '/tools/rebalance/output/curve_data.json': '../output/curve_data.json',
    '/tools/area_archetypes/restock.py': '../../area_archetypes/restock.py',
    '/tools/area_archetypes/area_archetypes.py': '../../area_archetypes/area_archetypes.py',
    '/tools/area_archetypes/archetypes.py': '../../area_archetypes/archetypes.py',
};

const BOOT = `
import json
import sys
sys.path.insert(0, '/tools/rebalance')
import rebalance as R
with open('/tools/rebalance/output/curve_data.json', encoding='utf-8') as f:
    SNAP = R.load_snapshot(json.load(f))
`;

// Writes FILES into Pyodide's file system (``fetchText(relative path)``
// reads one) and loads the snapshot. Returns {defaults, run(knobs)}:
// EXPLORER_KNOBS, and explore_run's result for a knob object.
export async function bootModel(pyodide, fetchText) {
    for (const [path, rel] of Object.entries(FILES)) {
        pyodide.FS.mkdirTree(path.slice(0, path.lastIndexOf('/')));
        pyodide.FS.writeFile(path, await fetchText(rel));
    }
    pyodide.runPython(BOOT);
    return {
        defaults: JSON.parse(pyodide.runPython('json.dumps(R.EXPLORER_KNOBS)')),
        run(knobs) {
            pyodide.globals.set('knobs_json', JSON.stringify(knobs));
            return JSON.parse(pyodide.runPython('json.dumps(R.explore_run(SNAP, json.loads(knobs_json)))'));
        },
    };
}
