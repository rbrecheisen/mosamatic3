const datasetSelect = document.getElementById('manual-editor-dataset-select');
const outputDatasetSelect = document.getElementById('manual-editor-output-dataset-select');
const caseSelect = document.getElementById('manual-editor-case-select');
const viewer = document.getElementById('manual-editor-viewer');
const statusEl = document.getElementById('manual-editor-status');
const saveButton = document.getElementById('manual-editor-save');
const undoButton = document.getElementById('manual-editor-undo');
const zoomButton = document.getElementById('manual-editor-zoom');
const resetZoomButton = document.getElementById('manual-editor-reset-zoom');

let datasets = [];
let outputDatasets = [];
let cases = [];
let currentCase = null;
let currentImage = null;
let currentMask = null;
let currentRows = 0;
let currentColumns = 0;
let currentLabel = 1;

let canvas = null;
let ctx = null;
let brushOverlayCanvas = null;
let brushOverlayCtx = null;
let lastBrushPreviewPoint = null;
let isPainting = false;
let lastPaintPoint = null;

let undoStack = [];
const maxUndoSteps = 20;

let viewport = null;

let isZoomMode = false;
let isZooming = false;
let zoomStartPoint = null;
let zoomCurrentPoint = null;

function setStatus(message) {
  statusEl.textContent = message || '';
}

function selectLabel(label) {
  currentLabel = label;

  const button = document.querySelector(`.manual-editor-toolbar button[data-label="${label}"]`);

  if (button) {
    document.querySelectorAll('.manual-editor-toolbar button[data-label]').forEach((item) => {
      item.classList.remove('selected');
    });

    button.classList.add('selected');
    setStatus(`Current label: ${button.textContent}`);
  }
}

function setZoomMode(enabled) {
  isZoomMode = enabled;
  isZooming = false;
  zoomStartPoint = null;
  zoomCurrentPoint = null;

  if (zoomButton) {
    zoomButton.classList.toggle('selected', isZoomMode);
  }

  clearBrushPreview();

  if (isZoomMode) {
    setStatus('Zoom mode: drag a rectangle on the image.');
  } else {
    setStatus(`Current label: ${currentLabel}`);
  }
}

function resetViewport() {
  if (!currentRows || !currentColumns) {
    viewport = null;
    return;
  }

  viewport = {
    x: 0,
    y: 0,
    width: currentColumns,
    height: currentRows,
  };

  renderCanvas();
  clearBrushPreview();
  setStatus('Zoom reset.');
}

function ensureViewport() {
  if (!viewport && currentRows && currentColumns) {
    viewport = {
      x: 0,
      y: 0,
      width: currentColumns,
      height: currentRows,
    };
  }
}

function canvasPointToImagePoint(canvasPoint) {
  ensureViewport();

  return {
    x: Math.round(viewport.x + (canvasPoint.x / currentColumns) * viewport.width),
    y: Math.round(viewport.y + (canvasPoint.y / currentRows) * viewport.height),
  };
}

function imagePointToCanvasPoint(imagePoint) {
  ensureViewport();

  return {
    x: ((imagePoint.x - viewport.x) / viewport.width) * currentColumns,
    y: ((imagePoint.y - viewport.y) / viewport.height) * currentRows,
  };
}

function clampImagePoint(point) {
  return {
    x: Math.max(0, Math.min(currentColumns - 1, point.x)),
    y: Math.max(0, Math.min(currentRows - 1, point.y)),
  };
}

function resetUndoStack() {
  undoStack = [];
  updateUndoButton();
}

function updateUndoButton() {
  undoButton.disabled = undoStack.length === 0;
}

function pushUndoState() {
  if (!currentMask) {
    return;
  }

  undoStack.push(new Uint8Array(currentMask));

  if (undoStack.length > maxUndoSteps) {
    undoStack.shift();
  }

  updateUndoButton();
}

function undoLastEdit() {
  if (undoStack.length === 0) {
    return;
  }

  currentMask = undoStack.pop();
  updateUndoButton();
  renderCanvas();
  setStatus('Undid last edit.');
}

function decodeBase64ToTypedArray(base64, TypedArrayConstructor) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);

  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }

  return new TypedArrayConstructor(bytes.buffer);
}

function encodeUint8ArrayToBase64(array) {
  let binary = '';
  const bytes = new Uint8Array(array.buffer);

  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }

  return btoa(binary);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': window.csrfToken,
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json();
}

async function loadDatasets() {
  setStatus('Loading datasets...');

  datasets = await fetchJson('/api/manual-editor/datasets');

  datasetSelect.innerHTML = '';

  if (datasets.length === 0) {
    datasetSelect.innerHTML = '<option value="">No editable datasets found</option>';
    setStatus('No output datasets with DICOM + segmentation files found.');
    return;
  }

  datasetSelect.innerHTML = '<option value="">Select dataset...</option>';

  for (const dataset of datasets) {
    const option = document.createElement('option');
    option.value = dataset.id;
    option.textContent = `${dataset.name} (${dataset.file_count} files)`;
    datasetSelect.appendChild(option);
  }

  setStatus('');
}

async function loadOutputDatasets(sourceDatasetId) {
  outputDatasetSelect.innerHTML = '<option value="">Loading correction datasets...</option>';

  outputDatasets = await fetchJson(
    `/api/manual-editor/datasets/${sourceDatasetId}/correction-datasets`,
  );

  outputDatasetSelect.innerHTML = '';

  const autoOption = document.createElement('option');
  autoOption.value = '';
  autoOption.textContent = outputDatasets.length === 0
    ? 'Auto-create correction dataset on first save'
    : 'Auto-use latest correction dataset';
  outputDatasetSelect.appendChild(autoOption);

  for (const dataset of outputDatasets) {
    const option = document.createElement('option');
    option.value = dataset.id;
    option.textContent = `${dataset.name} (${dataset.file_count} files)`;
    outputDatasetSelect.appendChild(option);
  }
}

async function loadCases(datasetId) {
  caseSelect.innerHTML = '<option value="">Loading cases...</option>';

  const outputDatasetId = outputDatasetSelect.value;
  const query = outputDatasetId
    ? `?output_dataset_id=${encodeURIComponent(outputDatasetId)}`
    : '';

  cases = await fetchJson(`/api/manual-editor/datasets/${datasetId}/cases${query}`);

  caseSelect.innerHTML = '';

  if (cases.length === 0) {
    caseSelect.innerHTML = '<option value="">No DICOM/segmentation pairs found</option>';
    return;
  }

  caseSelect.innerHTML = '<option value="">Select case...</option>';

  for (const item of cases) {
    const option = document.createElement('option');
    option.value = item.image_file_id;
    option.textContent = item.has_correction
      ? `${item.image_relative_path} corrected`
      : item.image_relative_path;
    caseSelect.appendChild(option);
  }
}

function ensureCanvas() {
  if (canvas && canvas.width === currentColumns && canvas.height === currentRows) {
    return;
  }

  viewer.innerHTML = '';

  canvas = document.createElement('canvas');
  canvas.className = 'manual-editor-canvas';
  canvas.width = currentColumns;
  canvas.height = currentRows;

  ctx = canvas.getContext('2d');

  brushOverlayCanvas = document.createElement('canvas');
  brushOverlayCanvas.className = 'manual-editor-brush-overlay';
  brushOverlayCanvas.width = currentColumns;
  brushOverlayCanvas.height = currentRows;

  brushOverlayCtx = brushOverlayCanvas.getContext('2d');

  canvas.addEventListener('pointerdown', handlePointerDown);
  canvas.addEventListener('pointermove', handlePointerMove);
  canvas.addEventListener('pointerup', handlePointerUp);
  canvas.addEventListener('pointercancel', handlePointerUp);
  canvas.addEventListener('pointerleave', handlePointerLeave);
  canvas.addEventListener('pointerenter', handlePointerEnter);

  viewer.appendChild(canvas);
  viewer.appendChild(brushOverlayCanvas);
}

function renderCanvas() {
  if (!currentImage || !currentMask) {
    return;
  }

  ensureCanvas();
  ensureViewport();

  const imageData = ctx.createImageData(currentColumns, currentRows);

  let min = Infinity;
  let max = -Infinity;

  for (const value of currentImage) {
    if (value < min) min = value;
    if (value > max) max = value;
  }

  const opacity = Number(document.getElementById('manual-editor-opacity').value) / 100;

  for (let canvasY = 0; canvasY < currentRows; canvasY += 1) {
    for (let canvasX = 0; canvasX < currentColumns; canvasX += 1) {
      const imageX = Math.max(
        0,
        Math.min(
          currentColumns - 1,
          Math.floor(viewport.x + (canvasX / currentColumns) * viewport.width),
        ),
      );

      const imageY = Math.max(
        0,
        Math.min(
          currentRows - 1,
          Math.floor(viewport.y + (canvasY / currentRows) * viewport.height),
        ),
      );

      const sourceIndex = imageY * currentColumns + imageX;
      const targetIndex = canvasY * currentColumns + canvasX;

      const gray = Math.max(
        0,
        Math.min(255, Math.round(((currentImage[sourceIndex] - min) / (max - min || 1)) * 255)),
      );

      let r = gray;
      let g = gray;
      let b = gray;

      const label = currentMask[sourceIndex];

      if (label === 1) {
        r = Math.round((1 - opacity) * gray + opacity * 255);
        g = Math.round((1 - opacity) * gray + opacity * 80);
        b = Math.round((1 - opacity) * gray + opacity * 80);
      } else if (label === 5) {
        r = Math.round((1 - opacity) * gray + opacity * 80);
        g = Math.round((1 - opacity) * gray + opacity * 255);
        b = Math.round((1 - opacity) * gray + opacity * 80);
      } else if (label === 7) {
        r = Math.round((1 - opacity) * gray + opacity * 80);
        g = Math.round((1 - opacity) * gray + opacity * 160);
        b = Math.round((1 - opacity) * gray + opacity * 255);
      }

      imageData.data[targetIndex * 4] = r;
      imageData.data[targetIndex * 4 + 1] = g;
      imageData.data[targetIndex * 4 + 2] = b;
      imageData.data[targetIndex * 4 + 3] = 255;
    }
  }

  ctx.putImageData(imageData, 0, 0);
}

function getCanvasPoint(event) {
  const rect = canvas.getBoundingClientRect();

  return {
    x: Math.floor(((event.clientX - rect.left) / rect.width) * currentColumns),
    y: Math.floor(((event.clientY - rect.top) / rect.height) * currentRows),
  };
}

function clearBrushPreview() {
  if (!brushOverlayCtx || !brushOverlayCanvas) {
    return;
  }

  brushOverlayCtx.clearRect(
    0,
    0,
    brushOverlayCanvas.width,
    brushOverlayCanvas.height,
  );
}

function drawBrushPreview(imagePoint) {
  if (!brushOverlayCtx || !brushOverlayCanvas || !imagePoint || isZoomMode) {
    return;
  }

  clearBrushPreview();

  const canvasPoint = imagePointToCanvasPoint(imagePoint);

  const brushSize = Number(document.getElementById('manual-editor-brush-size').value);
  const radiusInImagePixels = Math.max(1, brushSize / 2);
  const zoomScaleX = currentColumns / viewport.width;
  const zoomScaleY = currentRows / viewport.height;
  const radiusOnCanvas = radiusInImagePixels * ((zoomScaleX + zoomScaleY) / 2);

  brushOverlayCtx.save();
  brushOverlayCtx.beginPath();
  brushOverlayCtx.arc(canvasPoint.x, canvasPoint.y, radiusOnCanvas, 0, Math.PI * 2);
  brushOverlayCtx.setLineDash([4, 4]);
  brushOverlayCtx.lineWidth = 1.5;
  brushOverlayCtx.strokeStyle = 'white';
  brushOverlayCtx.stroke();
  brushOverlayCtx.restore();
}

function drawZoomRectangle() {
  if (!brushOverlayCtx || !brushOverlayCanvas || !zoomStartPoint || !zoomCurrentPoint) {
    return;
  }

  clearBrushPreview();

  const x = Math.min(zoomStartPoint.x, zoomCurrentPoint.x);
  const y = Math.min(zoomStartPoint.y, zoomCurrentPoint.y);
  const width = Math.abs(zoomCurrentPoint.x - zoomStartPoint.x);
  const height = Math.abs(zoomCurrentPoint.y - zoomStartPoint.y);

  brushOverlayCtx.save();
  brushOverlayCtx.setLineDash([6, 4]);
  brushOverlayCtx.lineWidth = 2;
  brushOverlayCtx.strokeStyle = 'white';
  brushOverlayCtx.strokeRect(x, y, width, height);

  brushOverlayCtx.fillStyle = 'rgba(255, 255, 255, 0.12)';
  brushOverlayCtx.fillRect(x, y, width, height);
  brushOverlayCtx.restore();
}

function applyZoomRectangle() {
  if (!zoomStartPoint || !zoomCurrentPoint) {
    return;
  }

  const minCanvasX = Math.min(zoomStartPoint.x, zoomCurrentPoint.x);
  const minCanvasY = Math.min(zoomStartPoint.y, zoomCurrentPoint.y);
  const maxCanvasX = Math.max(zoomStartPoint.x, zoomCurrentPoint.x);
  const maxCanvasY = Math.max(zoomStartPoint.y, zoomCurrentPoint.y);

  const rectWidth = maxCanvasX - minCanvasX;
  const rectHeight = maxCanvasY - minCanvasY;

  if (rectWidth < 5 || rectHeight < 5) {
    setStatus('Zoom rectangle too small.');
    return;
  }

  const topLeft = canvasPointToImagePoint({ x: minCanvasX, y: minCanvasY });
  const bottomRight = canvasPointToImagePoint({ x: maxCanvasX, y: maxCanvasY });

  let x = Math.min(topLeft.x, bottomRight.x);
  let y = Math.min(topLeft.y, bottomRight.y);
  let width = Math.abs(bottomRight.x - topLeft.x);
  let height = Math.abs(bottomRight.y - topLeft.y);

  const targetAspect = currentColumns / currentRows;
  const rectAspect = width / height;

  if (rectAspect > targetAspect) {
    const newHeight = width / targetAspect;
    y -= (newHeight - height) / 2;
    height = newHeight;
  } else {
    const newWidth = height * targetAspect;
    x -= (newWidth - width) / 2;
    width = newWidth;
  }

  x = Math.max(0, x);
  y = Math.max(0, y);

  if (x + width > currentColumns) {
    x = Math.max(0, currentColumns - width);
  }

  if (y + height > currentRows) {
    y = Math.max(0, currentRows - height);
  }

  viewport = {
    x,
    y,
    width: Math.min(width, currentColumns),
    height: Math.min(height, currentRows),
  };

  renderCanvas();
  clearBrushPreview();
  setZoomMode(false);
  setStatus('Zoomed to selected rectangle.');
}

function updateBrushPreview(event) {
  if (!canvas || !currentMask) {
    return;
  }

  lastBrushPreviewPoint = canvasPointToImagePoint(getCanvasPoint(event));
  drawBrushPreview(lastBrushPreviewPoint);
}

function handlePointerEnter(event) {
  updateBrushPreview(event);
}

function handlePointerLeave(event) {
  handlePointerUp(event);
  lastBrushPreviewPoint = null;
  clearBrushPreview();
}

function paintAt(x, y) {
  const brushSize = Number(document.getElementById('manual-editor-brush-size').value);
  const radius = Math.max(1, Math.floor(brushSize / 2));
  let changed = false;

  for (let yy = y - radius; yy <= y + radius; yy += 1) {
    for (let xx = x - radius; xx <= x + radius; xx += 1) {
      if (xx < 0 || yy < 0 || xx >= currentColumns || yy >= currentRows) {
        continue;
      }

      const dx = xx - x;
      const dy = yy - y;

      if (dx * dx + dy * dy <= radius * radius) {
        const index = yy * currentColumns + xx;

        if (currentMask[index] !== currentLabel) {
          currentMask[index] = currentLabel;
          changed = true;
        }
      }
    }
  }

  return changed;
}

function paintLine(from, to) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const distance = Math.max(Math.abs(dx), Math.abs(dy), 1);

  let changed = false;

  for (let step = 0; step <= distance; step += 1) {
    const t = step / distance;
    const x = Math.round(from.x + dx * t);
    const y = Math.round(from.y + dy * t);

    if (paintAt(x, y)) {
      changed = true;
    }
  }

  return changed;
}

function handlePointerDown(event) {
  if (!currentMask) {
    return;
  }

  event.preventDefault();

  canvas.setPointerCapture(event.pointerId);

  if (isZoomMode) {
    isZooming = true;
    zoomStartPoint = getCanvasPoint(event);
    zoomCurrentPoint = zoomStartPoint;
    drawZoomRectangle();
    return;
  }

  pushUndoState();

  isPainting = true;
  lastPaintPoint = canvasPointToImagePoint(getCanvasPoint(event));
  lastPaintPoint = clampImagePoint(lastPaintPoint);
  lastBrushPreviewPoint = lastPaintPoint;
  drawBrushPreview(lastBrushPreviewPoint);

  paintAt(lastPaintPoint.x, lastPaintPoint.y);
  renderCanvas();
}

function handlePointerMove(event) {
  if (!currentMask) {
    return;
  }

  event.preventDefault();

  const canvasPoint = getCanvasPoint(event);

  if (isZooming) {
    zoomCurrentPoint = canvasPoint;
    drawZoomRectangle();
    return;
  }

  const imagePoint = clampImagePoint(canvasPointToImagePoint(canvasPoint));
  lastBrushPreviewPoint = imagePoint;
  drawBrushPreview(imagePoint);

  if (!isPainting || !lastPaintPoint) {
    return;
  }

  const changed = paintLine(lastPaintPoint, imagePoint);

  lastPaintPoint = imagePoint;

  if (changed) {
    renderCanvas();
    drawBrushPreview(imagePoint);
  }
}

function handlePointerUp(event) {
  if (isZooming) {
    event.preventDefault();

    isZooming = false;
    applyZoomRectangle();

    zoomStartPoint = null;
    zoomCurrentPoint = null;

    try {
      canvas.releasePointerCapture(event.pointerId);
    } catch {
      // Ignore if pointer capture was already released.
    }

    return;
  }

  if (!isPainting) {
    return;
  }

  event.preventDefault();

  isPainting = false;
  lastPaintPoint = null;

  try {
    canvas.releasePointerCapture(event.pointerId);
  } catch {
    // Ignore if pointer capture was already released.
  }
}

async function loadCase(imageFileId) {
  currentCase = cases.find((item) => item.image_file_id === imageFileId);

  if (!currentCase) {
    return;
  }

  if (!currentCase.segmentation_file_id && !currentCase.correction_segmentation_file_id) {
    setStatus('This case has no segmentation file.');
    return;
  }

  setStatus('Loading image and mask...');

  const imagePayload = await fetchJson(`/api/manual-editor/files/${currentCase.image_file_id}/image`);

  const segmentationFileId =
    currentCase.correction_segmentation_file_id || currentCase.segmentation_file_id;

  const segmentationPayload = await fetchJson(
    `/api/manual-editor/files/${segmentationFileId}/segmentation`,
  );

  currentRows = imagePayload.rows;
  currentColumns = imagePayload.columns;
  currentImage = decodeBase64ToTypedArray(imagePayload.pixel_data_base64, Float32Array);
  currentMask = decodeBase64ToTypedArray(segmentationPayload.mask_base64, Uint8Array);

  canvas = null;
  ctx = null;
  brushOverlayCanvas = null;
  brushOverlayCtx = null;
  lastBrushPreviewPoint = null;
  viewport = null;
  setZoomMode(false);
  resetUndoStack();

  if (segmentationPayload.rows !== currentRows || segmentationPayload.columns !== currentColumns) {
    throw new Error('Image and segmentation dimensions do not match.');
  }

  renderCanvas();
  setStatus('');
}

async function saveCorrection() {
  if (!currentCase || !currentMask) {
    return;
  }

  setStatus('Saving correction...');

  const payload = {
    source_dataset_id: datasetSelect.value,
    output_dataset_id: outputDatasetSelect.value || null,
    rows: currentRows,
    columns: currentColumns,
    mask_base64: encodeUint8ArrayToBase64(currentMask),
  };

  const result = await fetchJson(
    `/api/manual-editor/files/${currentCase.image_file_id}/save-correction`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );

  currentCase.correction_image_file_id = result.output_image_file_id;
  currentCase.correction_image_relative_path = result.output_image_relative_path;
  currentCase.correction_segmentation_file_id = result.output_segmentation_file_id;
  currentCase.correction_segmentation_relative_path = result.output_segmentation_relative_path;
  currentCase.has_correction = true;

  if (!outputDatasetSelect.value) {
    await loadOutputDatasets(datasetSelect.value);
    outputDatasetSelect.value = result.output_dataset_id;
  }

  setStatus(`Saved to ${result.output_dataset_name}: ${result.output_segmentation_relative_path}`);
}

datasetSelect.addEventListener('change', async () => {
  if (!datasetSelect.value) {
    return;
  }

  currentCase = null;
  currentImage = null;
  currentMask = null;
  viewer.innerHTML = '';
  canvas = null;
  ctx = null;
  brushOverlayCanvas = null;
  brushOverlayCtx = null;
  lastBrushPreviewPoint = null;
  viewport = null;
  setZoomMode(false);
  resetUndoStack();

  await loadOutputDatasets(datasetSelect.value);
  await loadCases(datasetSelect.value);
});

outputDatasetSelect.addEventListener('change', async () => {
  if (!datasetSelect.value) {
    return;
  }

  currentCase = null;
  currentImage = null;
  currentMask = null;
  viewer.innerHTML = '';
  canvas = null;
  ctx = null;
  brushOverlayCanvas = null;
  brushOverlayCtx = null;
  lastBrushPreviewPoint = null;
  viewport = null;
  setZoomMode(false);
  resetUndoStack();

  await loadCases(datasetSelect.value);
});

caseSelect.addEventListener('change', async () => {
  if (!caseSelect.value) {
    return;
  }

  try {
    await loadCase(caseSelect.value);
  } catch (error) {
    console.error(error);
    setStatus(error.message);
  }
});

document.querySelectorAll('.manual-editor-toolbar button[data-label]').forEach((button) => {
  button.addEventListener('click', () => {
    selectLabel(Number(button.dataset.label));
  });
});

document.getElementById('manual-editor-opacity').addEventListener('input', () => {
  renderCanvas();
});

zoomButton.addEventListener('click', () => {
  setZoomMode(!isZoomMode);
});

resetZoomButton.addEventListener('click', () => {
  resetViewport();
});

undoButton.addEventListener('click', () => {
  undoLastEdit();
});

saveButton.addEventListener('click', async () => {
  try {
    await saveCorrection();
  } catch (error) {
    console.error(error);
    setStatus(error.message);
  }
});

document.getElementById('manual-editor-brush-size').addEventListener('input', () => {
  if (lastBrushPreviewPoint) {
    drawBrushPreview(lastBrushPreviewPoint);
  }
});

document.addEventListener('keydown', (event) => {
  const activeElement = document.activeElement;
  const isTyping =
    activeElement &&
    ['INPUT', 'SELECT', 'TEXTAREA'].includes(activeElement.tagName);

  if (isTyping) {
    return;
  }

  if (event.key === '1') {
    event.preventDefault();
    selectLabel(1);
  } else if (event.key === '5') {
    event.preventDefault();
    selectLabel(5);
  } else if (event.key === '7') {
    event.preventDefault();
    selectLabel(7);
  } else if (event.key === '0') {
    event.preventDefault();
    selectLabel(0);
  } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
    event.preventDefault();
    undoLastEdit();
  } else if (!event.ctrlKey && !event.metaKey && event.key.toLowerCase() === 'z') {
    event.preventDefault();
    setZoomMode(!isZoomMode);
  } else if (!event.ctrlKey && !event.metaKey && event.key.toLowerCase() === 'r') {
    event.preventDefault();
    resetViewport();
  }
});

loadDatasets().catch((error) => {
  console.error(error);
  setStatus(error.message);
});

selectLabel(1);