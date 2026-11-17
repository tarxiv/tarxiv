/* Clientside helpers for the object (lightcurve) page.
 *
 * Registers `window.dash_clientside.object_page`, wired up from
 * tarxiv/dashboard/pages/lightcurve.py via ClientsideFunction. The assets file
 * + explicit namespace form is used throughout this app because complex
 * inline-string clientside callbacks are unreliable under Dash 4 (see the
 * comments in lightcurve_aladin.js / cone_aladin.js).
 */
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.object_page = {
    /* Bring the tag card into view from the "Tag" button in the page head.
     * The tag card is the single place tags are managed, so rather than
     * duplicating the assign controls up top we jump to them and put the
     * cursor in the select. */
    scrollToTags: function (nClicks) {
        if (!nClicks) {
            return window.dash_clientside.no_update;
        }

        const card = document.getElementById("object-tag-card");
        if (!card) {
            return window.dash_clientside.no_update;
        }

        card.scrollIntoView({ behavior: "smooth", block: "center" });

        // Brief ring so it is obvious where the page landed.
        const previousTransition = card.style.transition;
        card.style.transition = "box-shadow 200ms ease";
        card.style.boxShadow = "0 0 0 2px var(--tarxiv-primary-ink)";
        setTimeout(function () {
            card.style.boxShadow = "";
            card.style.transition = previousTransition;
        }, 1200);

        // Focus the tag select once the scroll has settled, so the button
        // leaves the user ready to type.
        setTimeout(function () {
            const select = document.getElementById("assign-object-tag-select");
            if (select) {
                select.focus();
            }
        }, 400);

        return window.dash_clientside.no_update;
    },

    /* Collapse or expand a comment thread (lightcurve.render_thread) from
     * its +/- toggle or its line. Keeps the collapsed ids in
     * comment-collapsed-store so a server re-render of the list keeps them,
     * then redraws every thread from that store. */
    toggleThread: function (toggleClicks, lineClicks, collapsed, ids) {
        const ctx = window.dash_clientside.callback_context;
        const fired = ctx.triggered.filter(function (t) { return t.value; });
        if (!fired.length) {
            // New components rendering (n_clicks 0), not a click.
            return window.dash_clientside.no_update;
        }
        const clicked = JSON.parse(fired[0].prop_id.split(".")[0]).comment_id;
        const closed = new Set(collapsed || []);
        if (closed.has(clicked)) {
            closed.delete(clicked);
        } else {
            closed.add(clicked);
        }
        const isOpen = ids.map(function (id) { return !closed.has(id.comment_id); });
        return [
            Array.from(closed),
            isOpen,
            isOpen.map(function (o) { return o ? "\u2212" : "+"; }),
            isOpen.map(function (o) { return o ? "Collapse thread" : "Expand thread"; }),
            isOpen.map(function (o) {
                return "comment-thread-gutter comment-thread-line" + (o ? "" : " is-hidden");
            }),
        ];
    },
};
