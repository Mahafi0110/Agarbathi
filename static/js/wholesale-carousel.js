(function () {
  var carousel = document.querySelector("[data-wh-carousel]");
  if (!carousel) return;

  var track = carousel.querySelector(".wh-carousel-track");
  var slides = Array.from(carousel.querySelectorAll(".wh-carousel-slide"));
  var dots = Array.from(carousel.querySelectorAll(".wh-carousel-dot"));
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var currentIndex = 0;
  var paused = false;

  function showSlide(index) {
    currentIndex = (index + slides.length) % slides.length;
    track.style.transform = "translateX(-" + currentIndex * 100 + "%)";

    slides.forEach(function (slide, slideIndex) {
      slide.setAttribute("aria-hidden", slideIndex === currentIndex ? "false" : "true");
    });

    dots.forEach(function (dot, dotIndex) {
      if (dotIndex === currentIndex) dot.setAttribute("aria-current", "true");
      else dot.removeAttribute("aria-current");
      dot.classList.toggle("is-active", dotIndex === currentIndex);
    });
  }

  function advanceIfReady() {
    if (!paused && !document.hidden && !reducedMotion.matches) {
      showSlide(currentIndex + 1);
    }
  }

  carousel.querySelector(".wh-carousel-prev").addEventListener("click", function () {
    showSlide(currentIndex - 1);
  });

  carousel.querySelector(".wh-carousel-next").addEventListener("click", function () {
    showSlide(currentIndex + 1);
  });

  dots.forEach(function (dot, index) {
    dot.addEventListener("click", function () {
      showSlide(index);
    });
  });

  carousel.addEventListener("mouseenter", function () {
    paused = true;
  });

  carousel.addEventListener("mouseleave", function () {
    paused = false;
  });

  carousel.addEventListener("focusin", function () {
    paused = true;
  });

  carousel.addEventListener("focusout", function (event) {
    if (!carousel.contains(event.relatedTarget)) paused = false;
  });

  window.setInterval(advanceIfReady, 5000);
})();
