"""Small original bridge: GSAP, CSS animations and procedural drawing share one clock."""

SCRIPT = r'''
function attachAnimationClock(timeline, drawFrame, durationSeconds) {
    const duration = Number.isFinite(durationSeconds) ? durationSeconds : timeline.duration();
    let depth = 0;
    function sync(seconds) {
        for (const animation of document.getAnimations()) {
            const target = animation.effect && animation.effect.target;
            const host = target && target.closest && target.closest('[data-start]');
            const origin = Number(host && host.dataset.start) || 0;
            animation.pause();
            animation.currentTime = Math.max(0, seconds - origin) * 1000;
        }
        if (drawFrame) drawFrame(seconds);
    }
    // Preserve the GSAP object and chaining contract required by HyperFrames.
    // render() also covers native parent-timeline sampling; totalTime() covers
    // suppressed callbacks and repeated seeks to an unchanged time.
    for (const name of ['render', 'totalTime']) {
        const original = timeline[name];
        timeline[name] = function(...args) {
            if (name === 'totalTime' && args.length === 0) return original.call(this);
            depth++;
            try { return original.apply(this, args); }
            finally { if (--depth === 0) sync(this.time()); }
        };
    }
    window.__seek = seconds => {
        if (typeof seconds !== 'number' || !Number.isFinite(seconds)) throw new Error('Invalid frame time');
        timeline.pause();
        timeline.totalTime(Math.max(0, Math.min(duration, seconds)), true);
        return true;
    };
    // Also implement the public Opuscar core composition contract.
    window.DUR = duration;
    window.render = window.__seek;
    window.READY = false;
    window.__ready = document.fonts.ready.then(() => {
        sync(timeline.time());
        window.READY = true;
        return true;
    });
    sync(timeline.time());
}
'''
