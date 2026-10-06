document.addEventListener("DOMContentLoaded", function () {
    const counters = document.querySelectorAll(".stat-number");

    const duration = 2000;
    const startTime = performance.now();

    function updateCounters(currentTime) {
        const progress = Math.min(
            (currentTime - startTime) / duration,
            1
        );

        counters.forEach(function (counter) {
            const target = Number(counter.dataset.target);
            const suffix = counter.dataset.suffix || "";

            counter.textContent = Math.floor(target * progress) + suffix;
        });

        if (progress < 1) {
            requestAnimationFrame(updateCounters);
        }
    }

    requestAnimationFrame(updateCounters);
});