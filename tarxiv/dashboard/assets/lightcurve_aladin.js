/* Clientside callback for the object-page Aladin Lite widget.
 *
 * Registers `window.dash_clientside.lightcurve_aladin.initialize`, wired up
 * from tarxiv/dashboard/pages/lightcurve.py via ClientsideFunction. Doing it
 * this way (assets file + explicit namespace) avoids the
 * `dc[namespace][function_name] is undefined` errors that can occur with
 * complex inline-string clientside callbacks under Dash 4, and matches
 * cone_aladin.js.
 *
 * Centres the sky view on the object and marks its position. The page is
 * server-rendered, so this polls for the container rather than watching the
 * whole document for Plotly to appear (which the previous inline version did,
 * and which broke whenever the DOM order changed).
 */
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.lightcurve_aladin = {
    initialize: function (storeData) {
        if (
            !storeData ||
            storeData.ra_deg === null ||
            storeData.ra_deg === undefined ||
            storeData.dec_deg === null ||
            storeData.dec_deg === undefined
        ) {
            return "No coordinates available for Aladin";
        }

        const ra = storeData.ra_deg;
        const dec = storeData.dec_deg;
        // Wide enough to show the host galaxy context, tight enough to place
        // the transient within it.
        const fov = 0.1;

        let attempts = 0;

        function initAladin() {
            const container = document.getElementById("aladin-lite-div");
            if (!container || !window.A) {
                // Give up after ~10s rather than polling forever.
                if (attempts++ > 100) {
                    console.warn("Aladin Lite did not become available");
                    return;
                }
                setTimeout(initAladin, 100);
                return;
            }

            window.A.init.then(function () {
                container.innerHTML = "";
                const aladin = window.A.aladin("#aladin-lite-div", {
                    survey: "P/PanSTARRS/DR1/color-z-zg-g",
                    target: ra + " " + dec,
                    fov: fov,
                    showFullscreenControl: true,
                    showLayersControl: false,
                    showFrame: false,
                    reticleColor: "#e34948",
                });

                try {
                    const catalog = window.A.catalog({
                        shape: "circle",
                        color: "#e34948",
                        sourceSize: 16,
                    });
                    aladin.addCatalog(catalog);
                    catalog.addSources([
                        window.A.source(ra, dec, { name: storeData.source || "object" }),
                    ]);
                } catch (err) {
                    console.warn("Aladin marker overlay failed:", err);
                }
            });
        }

        initAladin();
        return "Aladin initialised";
    },
};
