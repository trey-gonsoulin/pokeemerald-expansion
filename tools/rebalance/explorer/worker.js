// Runs the model off the page's thread: posts {type: 'ready', defaults}
// once loaded, then {type: 'result', id, result, ms} for each
// {id, knobs} it gets, or {type: 'error', id, message}.
import { PYODIDE_URL, bootModel } from './model.js';

const ready = (async () => {
    const { loadPyodide } = await import(PYODIDE_URL + 'pyodide.mjs');
    const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
    const model = await bootModel(pyodide, async rel => {
        const res = await fetch(new URL(rel, import.meta.url));
        if (!res.ok)
            throw new Error(`${rel}: HTTP ${res.status}`);
        return res.text();
    });
    postMessage({ type: 'ready', defaults: model.defaults });
    return model;
})();
ready.catch(err => postMessage({ type: 'error', message: String(err) }));

onmessage = async ({ data }) => {
    try {
        const model = await ready;
        const start = performance.now();
        const result = model.run(data.knobs);
        postMessage({ type: 'result', id: data.id, result, ms: performance.now() - start });
    } catch (err) {
        postMessage({ type: 'error', id: data.id, message: String(err) });
    }
};
