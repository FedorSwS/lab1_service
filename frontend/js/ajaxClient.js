// Кроссбраузерное создание XMLHttpRequest (согласно методическим указаниям)
function createRequest() {
  var req = null;
  try {
    req = new XMLHttpRequest();
  } catch (e1) {
    try { req = new ActiveXObject("Msxml2.XMLHTTP"); }
    catch (e2) {
      try { req = new ActiveXObject("Microsoft.XMLHTTP"); }
      catch (e3) { req = null; }
    }
  }
  return req;
}

function generateIdempotencyKey() {
  return 'idem-' + Date.now() + '-' + Math.random().toString(36).substring(2, 10);
}

function incrementUpdateCounter() {
  var el = document.getElementById('jqCounter');
  if (el) el.value = String(parseInt(el.value || '0', 10) + 1);
}

function checkSkuAvailability() {
  var sku = document.getElementById('skuInput').value.trim();
  if (!sku) return;
  var req = createRequest();
  req.open('GET', '/api/products/check?sku=' + encodeURIComponent(sku), true);
  req.onreadystatechange = function () {
    if (req.readyState === 4 && req.status === 200) {
      var data = JSON.parse(req.responseText);
      document.getElementById('skuStatus').value = data.available ? ('В наличии: ' + data.stock_qty) : 'Нет в наличии';
      incrementUpdateCounter();
    }
  };
  req.send(null);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, function (ch) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
  });
}

function loadCatalog() {
  var req = createRequest();
  req.open('GET', '/api/products', true);
  req.onreadystatechange = function () {
    if (req.readyState === 4 && req.status === 200) {
      var data = JSON.parse(req.responseText);
      var box = document.getElementById('catalogList');
      if (!data.items.length) {
        box.innerHTML = 'Каталог пуст';
        return;
      }
      box.innerHTML = data.items.map(function (p) {
        return '<article class="card">' +
          '<h3>' + escapeHtml(p.name) + '</h3>' +
          '<p>' + escapeHtml(p.sku) + ' · ' + p.price_rub + ' ₽</p>' +
          '<p>В наличии: ' + p.stock_qty + '</p>' +
          '<button type="button" onclick="addToCart(' + p.id + ',' + p.version + ')">В корзину</button>' +
          '</article>';
      }).join('');
      incrementUpdateCounter();
    }
  };
  req.send(null);
}

function addToCart(productId, expectedVersion) {
  var req = createRequest();
  var idemKey = generateIdempotencyKey();
  req.open('POST', '/api/cart/add', true);
  req.setRequestHeader('Content-Type', 'application/json');
  req.setRequestHeader('Idempotency-Key', idemKey);
  req.onreadystatechange = function () {
    if (req.readyState === 4) {
      incrementUpdateCounter();
      loadCatalog();
      loadCart();
    }
  };
  req.send(JSON.stringify({ product_id: productId, qty: 1, expected_version: expectedVersion }));
}

function removeFromCart(cartItemId) {
  var req = createRequest();
  req.open('DELETE', '/api/cart/item/' + encodeURIComponent(cartItemId), true);
  req.setRequestHeader('Idempotency-Key', generateIdempotencyKey());
  req.onreadystatechange = function () {
    if (req.readyState === 4) {
      incrementUpdateCounter();
      loadCatalog();
      loadCart();
    }
  };
  req.send(null);
}

function loadCart() {
  var req = createRequest();
  req.open('GET', '/api/cart', true);
  req.onreadystatechange = function () {
    if (req.readyState === 4 && req.status === 200) {
      var data = JSON.parse(req.responseText);
      var box = document.getElementById('cartItems');
      if (!data.items.length) {
        box.innerHTML = 'Корзина пуста';
      } else {
        box.innerHTML = data.items.map(function (it) {
          return '<div>' + it.name + ' x ' + it.qty + ' = ' + (it.price_rub * it.qty) +
                 ' ₽ <button class="danger" onclick="removeFromCart(' + it.id + ')">Удалить</button></div>';
        }).join('');
      }
      document.getElementById('cartTotal').textContent = data.total_rub + ' ₽';
    }
  };
  req.send(null);
}
