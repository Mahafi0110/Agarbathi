/* Cart lives in the browser's localStorage. The server re-prices everything at checkout. */
(function () {
  var KEY = "pooja_cart";
  var MAX_QTY = 500;

  function load() {
    try {
      var data = JSON.parse(localStorage.getItem(KEY) || "[]");
      return Array.isArray(data) ? data : [];
    } catch (e) { return []; }
  }
  function save(items) {
    try { localStorage.setItem(KEY, JSON.stringify(items)); } catch (e) {}
    renderBadge(items);
  }
  function unit(it) {   // wholesale price once the minimum packs are reached
    var w = parseFloat(it.wprice), m = parseInt(it.wmin, 10);
    return (w && m && it.qty >= m) ? w : parseFloat(it.price);
  }
  function count(items) { return items.reduce(function (n, i) { return n + i.qty; }, 0); }
  function total(items) { return items.reduce(function (n, i) { return n + i.qty * unit(i); }, 0); }
  function money(n) { return "\u20B9" + n.toFixed(2); }

  function renderBadge(items) {
    var el = document.getElementById("cart-count");
    if (el) el.textContent = count(items);
  }

  function add(ds) {
    var items = load();
    var found = items.find(function (i) { return String(i.id) === ds.id; });
    if (found) { found.qty = Math.min(MAX_QTY, found.qty + 1); }
    else { items.push({ id: ds.id, title: ds.title, price: ds.price, image: ds.image, slug: ds.slug, wprice: ds.wprice || "", wmin: ds.wmin || "", qty: 1 }); }
    save(items);
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".add-to-cart");
    if (!btn) return;
    add(btn.dataset);
    var old = btn.textContent;
    btn.textContent = "Added";
    btn.disabled = true;
    setTimeout(function () { btn.textContent = old; btn.disabled = false; }, 1200);
  });

  /* Cart page */
  var list = document.getElementById("cart-lines");
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;   // textContent: safe against injected markup
    return n;
  }
  function setQty(id, q) {
    var items = load();
    items.forEach(function (i) { if (i.id === id) i.qty = Math.max(1, Math.min(MAX_QTY, q || 1)); });
    save(items); renderCart();
  }
  function renderCart() {
    var items = load();
    document.getElementById("cart-empty").hidden = items.length > 0;
    document.getElementById("cart-wrap").hidden = items.length === 0;
    list.textContent = "";
    items.forEach(function (it) {
      var li = el("li", "line");
      if (it.image) { var img = el("img"); img.src = it.image; img.alt = ""; li.appendChild(img); }
      var info = el("div", "line-info");
      var a = el("a", "", it.title); a.href = "/product/" + encodeURIComponent(it.slug) + "/";
      info.appendChild(a);
      var wholesale = parseFloat(it.wprice) && parseInt(it.wmin, 10) && it.qty >= parseInt(it.wmin, 10);
      info.appendChild(el("span", "", money(unit(it)) + " each" + (wholesale ? " (wholesale rate)" :
        (parseFloat(it.wprice) ? " \u00B7 " + money(parseFloat(it.wprice)) + " at " + it.wmin + "+ packs" : ""))));
      li.appendChild(info);

      var qty = el("div", "qty");
      var minus = el("button", "", "\u2212"); minus.type = "button"; minus.setAttribute("aria-label", "Decrease quantity");
      var num = el("input"); num.type = "number"; num.min = "1"; num.max = String(MAX_QTY); num.value = String(it.qty);
      num.setAttribute("aria-label", "Quantity");
      var plus = el("button", "", "+"); plus.type = "button"; plus.setAttribute("aria-label", "Increase quantity");
      minus.onclick = function () { setQty(it.id, it.qty - 1); };
      plus.onclick = function () { setQty(it.id, it.qty + 1); };
      num.onchange = function () { setQty(it.id, parseInt(num.value, 10)); };
      qty.append(minus, num, plus);
      li.appendChild(qty);

      li.appendChild(el("strong", "line-total", money(it.qty * unit(it))));
      var rm = el("button", "link", "Remove"); rm.type = "button";
      rm.onclick = function () { save(load().filter(function (i) { return i.id !== it.id; })); renderCart(); };
      li.appendChild(rm);
      list.appendChild(li);
    });
    var wrap = document.getElementById("cart-wrap");
    var freeAbove = parseFloat(wrap.dataset.freeAbove), fee = parseFloat(wrap.dataset.fee);
    var sub = total(items), ship = sub >= freeAbove ? 0 : fee;
    document.getElementById("cart-subtotal").textContent = money(sub);
    document.getElementById("cart-shipping").textContent = ship ? money(ship) : "Free";
    document.getElementById("cart-total").textContent = money(sub + ship);
    document.getElementById("ship-note").textContent = ship
      ? "Add " + money(freeAbove - sub) + " more to get free delivery."
      : "You have free delivery on this order.";
  }

  renderBadge(load());
  if (list) {
    renderCart();
    document.getElementById("checkout-form").addEventListener("submit", function () {
      document.getElementById("cart-json").value = JSON.stringify(
        load().map(function (i) { return { id: i.id, qty: i.qty }; })
      );
    });
  }
})();
