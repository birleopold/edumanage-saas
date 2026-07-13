(function () {
  "use strict";

  function values(config) {
    var datasets = (config.data && config.data.datasets) || [];
    return datasets.map(function (dataset) {
      return (dataset.data || []).map(function (value) { return Number(value) || 0; });
    });
  }

  function colors(dataset, fallback) {
    var color = dataset.backgroundColor || dataset.borderColor || fallback;
    return Array.isArray(color) ? color : [color];
  }

  function canvasFrom(target) {
    if (target && target.canvas) return target.canvas;
    return target;
  }

  function clear(ctx, canvas) {
    var ratio = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    var width = rect.width || canvas.width || 640;
    var height = Number(canvas.getAttribute("height")) || rect.height || 260;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    return { width: width, height: height };
  }

  function drawLegend(ctx, labels, colorList, width, y) {
    ctx.font = "12px system-ui, sans-serif";
    ctx.textBaseline = "middle";
    var x = 16;
    labels.forEach(function (label, index) {
      ctx.fillStyle = colorList[index % colorList.length] || "#2563eb";
      ctx.fillRect(x, y - 5, 10, 10);
      ctx.fillStyle = "#475569";
      ctx.fillText(String(label), x + 16, y);
      x += Math.max(86, ctx.measureText(String(label)).width + 34);
      if (x > width - 120) {
        x = 16;
        y += 18;
      }
    });
  }

  function bar(ctx, canvas, config) {
    var size = clear(ctx, canvas);
    var labels = (config.data && config.data.labels) || [];
    var dataset = ((config.data && config.data.datasets) || [])[0] || {};
    var data = values(config)[0] || [];
    var max = Math.max.apply(null, data.concat([1]));
    var palette = colors(dataset, "#2563eb");
    var plotX = 42;
    var plotY = 20;
    var plotW = size.width - 64;
    var plotH = size.height - 68;
    var gap = 10;
    var barW = Math.max(10, (plotW - gap * (data.length - 1)) / Math.max(data.length, 1));
    ctx.strokeStyle = "#e2e8f0";
    ctx.beginPath();
    ctx.moveTo(plotX, plotY);
    ctx.lineTo(plotX, plotY + plotH);
    ctx.lineTo(plotX + plotW, plotY + plotH);
    ctx.stroke();
    data.forEach(function (value, index) {
      var h = (value / max) * (plotH - 10);
      var x = plotX + index * (barW + gap);
      var y = plotY + plotH - h;
      ctx.fillStyle = palette[index % palette.length] || palette[0];
      ctx.fillRect(x, y, barW, h);
      ctx.fillStyle = "#475569";
      ctx.font = "11px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(String(labels[index] || ""), x + barW / 2, plotY + plotH + 16);
    });
  }

  function line(ctx, canvas, config) {
    var size = clear(ctx, canvas);
    var labels = (config.data && config.data.labels) || [];
    var datasets = (config.data && config.data.datasets) || [];
    var all = values(config).reduce(function (acc, row) { return acc.concat(row); }, []);
    var max = Math.max.apply(null, all.concat([1]));
    var plotX = 42;
    var plotY = 20;
    var plotW = size.width - 64;
    var plotH = size.height - 72;
    ctx.strokeStyle = "#e2e8f0";
    ctx.beginPath();
    ctx.moveTo(plotX, plotY);
    ctx.lineTo(plotX, plotY + plotH);
    ctx.lineTo(plotX + plotW, plotY + plotH);
    ctx.stroke();
    datasets.forEach(function (dataset, datasetIndex) {
      var data = (dataset.data || []).map(Number);
      var color = dataset.borderColor || colors(dataset, "#2563eb")[0] || "#2563eb";
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      data.forEach(function (value, index) {
        var x = plotX + (plotW / Math.max(data.length - 1, 1)) * index;
        var y = plotY + plotH - ((value || 0) / max) * (plotH - 10);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      drawLegend(ctx, [dataset.label || "Series " + (datasetIndex + 1)], [color], size.width, size.height - 20 - datasetIndex * 18);
    });
    ctx.fillStyle = "#475569";
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "center";
    labels.forEach(function (label, index) {
      if (index % Math.ceil(labels.length / 5 || 1) === 0) {
        ctx.fillText(String(label), plotX + (plotW / Math.max(labels.length - 1, 1)) * index, plotY + plotH + 16);
      }
    });
  }

  function doughnut(ctx, canvas, config) {
    var size = clear(ctx, canvas);
    var labels = (config.data && config.data.labels) || [];
    var dataset = ((config.data && config.data.datasets) || [])[0] || {};
    var data = values(config)[0] || [];
    var palette = colors(dataset, "#2563eb");
    var total = data.reduce(function (sum, value) { return sum + value; }, 0) || 1;
    var radius = Math.min(size.width, size.height - 40) / 2 - 12;
    var cx = size.width / 2;
    var cy = (size.height - 34) / 2;
    var start = -Math.PI / 2;
    data.forEach(function (value, index) {
      var angle = (value / total) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, radius, start, start + angle);
      ctx.closePath();
      ctx.fillStyle = palette[index % palette.length] || palette[0];
      ctx.fill();
      start += angle;
    });
    ctx.globalCompositeOperation = "destination-out";
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 0.58, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalCompositeOperation = "source-over";
    drawLegend(ctx, labels, palette, size.width, size.height - 18);
  }

  window.Chart = function Chart(target, config) {
    var canvas = canvasFrom(target);
    var ctx = canvas.getContext("2d");
    var type = (config && config.type) || "bar";
    if (type === "doughnut" || type === "pie") doughnut(ctx, canvas, config);
    else if (type === "line") line(ctx, canvas, config);
    else bar(ctx, canvas, config);
    return { destroy: function () { clear(ctx, canvas); } };
  };
})();
