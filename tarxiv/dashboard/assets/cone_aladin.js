/* Clientside callbacks for the cone-search Aladin Lite widget.
 *
 * Registers `window.dash_clientside.cone_aladin.initialize`, which is wired
 * up from tarxiv/dashboard/pages/cone.py via ClientsideFunction. Doing it
 * this way (assets file + explicit namespace) avoids the
 * `dc[namespace][function_name] is undefined` errors that can occur with
 * complex inline-string clientside callbacks under Dash 4.
 *
 * Initialises the Aladin Lite widget for cone-search results: centres on the
 * search position, draws the search radius as a subtle ring, drops a marker
 * per result, and hooks up hover-linking from result cards to marker
 * highlights. The hover handler uses event delegation so it survives
 * pagination of the result list (cards are added/removed as the user
 * changes pages).
 */
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.cone_aladin = {
    initialize: function (storeData) {
        if (!storeData || !storeData.results) {
            return "No cone search results";
        }

        const ra = storeData.ra;
        const dec = storeData.dec;
        const results = storeData.results;
        const radiusArcsec = storeData.radius || 60;
        const radiusDeg = radiusArcsec / 3600;
        // FOV in degrees: encompass the search radius with padding (min 0.02 deg).
        const fov = Math.max(radiusDeg * 3, 0.02);

        function initAladin() {
            const container = document.getElementById("cone-aladin-div");
            if (!container || !window.A) {
                setTimeout(initAladin, 100);
                return;
            }

            window.A.init.then(function () {
                container.innerHTML = "";
                const aladin = window.A.aladin("#cone-aladin-div", {
                    survey: "P/PanSTARRS/DR1/color-z-zg-g",
                    target: ra + " " + dec,
                    fov: fov,
                });

                try {
                    // Subtle search-radius ring around the centre.
                    const radiusOverlay = window.A.graphicOverlay({
                        color: "rgba(255, 165, 0, 0.55)",
                        lineWidth: 1,
                    });
                    aladin.addOverlay(radiusOverlay);
                    radiusOverlay.add(
                        window.A.circle(ra, dec, radiusDeg, {
                            color: "rgba(255, 165, 0, 0.55)",
                        })
                    );
                } catch (err) {
                    console.warn("Aladin radius overlay failed:", err);
                }

                let highlightCat = null;
                try {
                    // Search-centre marker.
                    const centreCat = window.A.catalog({
                        name: "Search centre",
                        sourceSize: 16,
                        color: "red",
                    });
                    aladin.addCatalog(centreCat);
                    centreCat.addSources([
                        window.A.marker(ra, dec, { popupTitle: "Search centre" }),
                    ]);

                    // One marker per result.
                    const resultCat = window.A.catalog({
                        name: "Results",
                        sourceSize: 12,
                        color: "#1c7ed6",
                    });
                    aladin.addCatalog(resultCat);
                    resultCat.addSources(
                        results.map(function (o) {
                            return window.A.marker(o.ra, o.dec, {
                                popupTitle: o.obj_name,
                                popupDesc: "RA " + o.ra + ", Dec " + o.dec,
                            });
                        })
                    );

                    highlightCat = window.A.catalog({
                        name: "Highlight",
                        sourceSize: 20,
                        color: "orange",
                    });
                    aladin.addCatalog(highlightCat);
                } catch (err) {
                    console.warn("Aladin marker overlay failed:", err);
                }

                // Event-delegated hover-linking. Result cards are pattern-
                // matching components whose DOM id is a JSON string carrying
                // the absolute result index — parse that to look up the
                // marker, so it works regardless of which page is shown.
                if (window.__tarxivConeHover) {
                    document.body.removeEventListener(
                        "mouseover",
                        window.__tarxivConeHover.over
                    );
                    document.body.removeEventListener(
                        "mouseout",
                        window.__tarxivConeHover.out
                    );
                }
                function cardIndex(el) {
                    const card =
                        el && el.closest && el.closest('[id*="object-card"]');
                    if (!card || !card.id) return null;
                    let parsed;
                    try {
                        parsed = JSON.parse(card.id);
                    } catch (e) {
                        return null;
                    }
                    if (!parsed || parsed.type !== "object-card") return null;
                    return parsed.index;
                }
                const over = function (e) {
                    if (!highlightCat) return;
                    const idx = cardIndex(e.target);
                    if (idx == null) return;
                    const o = results[idx];
                    if (!o) return;
                    highlightCat.removeAll();
                    highlightCat.addSources([
                        window.A.marker(o.ra, o.dec, { popupTitle: o.obj_name }),
                    ]);
                };
                const out = function (e) {
                    if (!highlightCat) return;
                    if (cardIndex(e.target) == null) return;
                    highlightCat.removeAll();
                };
                document.body.addEventListener("mouseover", over);
                document.body.addEventListener("mouseout", out);
                window.__tarxivConeHover = { over: over, out: out };
            });
        }

        initAladin();
        return "Aladin cone init";
    },
};
