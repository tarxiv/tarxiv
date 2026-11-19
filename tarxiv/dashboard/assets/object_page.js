/* Clientside helpers for the object (lightcurve) page.
 *
 * Registers `window.dash_clientside.object_page`, wired up from
 * tarxiv/dashboard/pages/lightcurve.py via ClientsideFunction. The assets file
 * + explicit namespace form is used throughout this app because complex
 * inline-string clientside callbacks are unreliable under Dash 4 (see the
 * comments in lightcurve_aladin.js / cone_aladin.js).
 */
window.dash_clientside = window.dash_clientside || {};
/* Scroll `ringId` into view, ring it briefly so it is obvious where the page
 * landed, then focus `focusId` once the scroll has settled so the user can
 * type straight away. Missing elements (e.g. logged out) are a no-op. */
function objectPageJumpTo(ringId, focusId) {
    const target = document.getElementById(ringId);
    if (!target) {
        return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "center" });

    const previousTransition = target.style.transition;
    target.style.transition = "box-shadow 200ms ease";
    target.style.boxShadow = "0 0 0 2px var(--tarxiv-primary-ink)";
    setTimeout(function () {
        target.style.boxShadow = "";
        target.style.transition = previousTransition;
    }, 1200);

    setTimeout(function () {
        const field = document.getElementById(focusId);
        if (field) {
            field.focus({ preventScroll: true });
        }
    }, 400);
}

window.dash_clientside.object_page = {
    /* "Tag" in the page head: the tag card is the single place tags are
     * managed, so jump to it rather than duplicating its controls up top. */
    scrollToTags: function (nClicks) {
        if (nClicks) {
            objectPageJumpTo("object-tag-card", "assign-object-tag-select");
        }
        return window.dash_clientside.no_update;
    },

    /* "Comment" in the page head: jump to the comment box, wherever it
     * currently sits (bottom of the list, or inside a reply/edit). */
    scrollToComments: function (nClicks) {
        if (nClicks) {
            objectPageJumpTo("comment-body", "comment-body");
        }
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
            isOpen.map(function (o) { return o ? "Collapse thread" : "Expand thread"; }),
            isOpen.map(function (o) {
                return "comment-thread-gutter" + (o ? "" : " is-collapsed");
            }),
        ];
    },
};
