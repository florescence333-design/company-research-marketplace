const DEFAULT_FILL = '#e9f4ed';
const DEFAULT_STROKE = '#397a58';
const DARK_TEXT = '#1a1a1a';
const LIGHT_TEXT = '#ffffff';

function colorChannels(color) {
  const hex = /^#([\da-f]{6})$/i.exec(color || '');
  if (hex) return [0, 2, 4].map(offset => parseInt(hex[1].slice(offset, offset + 2), 16));
  const rgb = /^rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/i.exec(color || '');
  return rgb ? rgb.slice(1, 4).map(Number) : null;
}

function luminance(color) {
  const channels = colorChannels(color);
  if (!channels) return null;
  const [red, green, blue] = channels.map(value => {
    const channel = value / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return red * 0.2126 + green * 0.7152 + blue * 0.0722;
}

export function diagramTextColor(fill) {
  const background = luminance(fill);
  if (background === null) return DARK_TEXT;
  const dark = luminance(DARK_TEXT);
  const darkContrast = (background + 0.05) / (dark + 0.05);
  const lightContrast = 1.05 / (background + 0.05);
  return darkContrast >= lightContrast ? DARK_TEXT : LIGHT_TEXT;
}

export function diagramWidth(naturalWidth) {
  return Math.max(720, Math.ceil(naturalWidth * 0.84));
}

export function styleDiagramNodes(svg) {
  if (!svg) return;
  for (const node of svg.querySelectorAll('.node')) {
    const shape = node.querySelector('.label-container');
    const label = node.querySelector('.label');
    if (!shape || !label) continue;
    if (!shape.style.getPropertyValue('fill')) {
      shape.style.setProperty('fill', DEFAULT_FILL, 'important');
      shape.style.setProperty('stroke', DEFAULT_STROKE, 'important');
    }
    const textColor = diagramTextColor(getComputedStyle(shape).fill);
    label.style.setProperty('color', textColor, 'important');
    for (const element of label.querySelectorAll('div, p, span')) {
      element.style.setProperty('color', textColor, 'important');
    }
    for (const element of label.querySelectorAll('text, tspan')) {
      element.style.setProperty('fill', textColor, 'important');
    }
  }
}
