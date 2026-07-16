// 机械风「调取档案」启动序列。Material 换页(document$)后重播；尊重 reduce-motion。
(function () {
  function boot() {
    var inner = document.querySelector(".md-content__inner");
    if (!inner) return;
    // 清理上一次注入的特效元素，避免重复堆叠
    inner.querySelectorAll(".cx-scan,.cx-bracket").forEach(function (e) { e.remove(); });
    inner.classList.remove("cx-booting");
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return; // 直显最终态，不做动画
    }
    inner.style.position = "relative";
    var scan = document.createElement("span");
    scan.className = "cx-scan";
    inner.appendChild(scan);
    var corners = [["tl", "16px", "16px"], ["tr", "-16px", "16px"],
                   ["bl", "16px", "-16px"], ["br", "-16px", "-16px"]];
    corners.forEach(function (c, i) {
      var b = document.createElement("span");
      b.className = "cx-bracket cx-" + c[0];
      b.style.setProperty("--dx", c[1]);
      b.style.setProperty("--dy", c[2]);
      b.style.animationDelay = (0.05 + i * 0.07) + "s";
      inner.appendChild(b);
    });
    void inner.offsetWidth;      // 强制回流，确保重复触发动画
    inner.classList.add("cx-booting");
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(boot);   // Material 每次换页触发
  } else {
    document.addEventListener("DOMContentLoaded", boot);
  }
})();
