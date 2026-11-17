/* Loads Aladin Lite and exposes it as `window.A`.
 *
 * aladin-lite's npm build is ESM-only (it ends in `export default`), so it
 * can't be included as a plain <script> via Dash's external_scripts: that
 * throws "Unexpected token 'export'" and window.A is never set. A dynamic
 * import() works from this classic script. lightcurve_aladin.js and
 * cone_aladin.js poll for window.A before initialising.
 */
import("https://cdn.jsdelivr.net/npm/aladin-lite@3.8.2/dist/aladin.js")
    .then(function (m) {
        window.A = m.default;
    })
    .catch(function (err) {
        console.warn("Aladin Lite failed to load:", err);
    });
