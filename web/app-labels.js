'use strict';

function displayLabel(value, fallback = '') {
  const text = String(value || '').trim();
  if (isBadDisplayHint(text) || isMixedNameTitleLabel(text)) return isBadDisplayHint(fallback) ? '' : friendlyKey(fallback);
  const translated = koreanLabelFromText(text, fallback);
  return genericDisplayName(text) || translated || text || friendlyKey(fallback);
}

function isBadDisplayHint(value) {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, '');
  return ['잘못된힌트', 'wronghint', 'badhint', 'invalidhint'].includes(normalized);
}

function hasHangul(value) {
  return /[가-힣]/.test(String(value || ''));
}

function isMixedNameTitleLabel(value) {
  const text = String(value || '').trim();
  if (!text) return false;
  const lower = text.toLowerCase();
  if (!/[a-z]/.test(lower)) return false;
  if (/\b([a-z]{2,})\b.*\b\1\b/.test(lower)) return true;
  if (hasHangul(text) && /\b[a-z]{2,}\b/.test(lower) && /\b\d{1,2}\b$/.test(lower)) return true;
  return hasHangul(text) && /\b[a-z]{2,}\b/.test(lower) && text.split(/\s+/).length <= 5;
}

function hasCjk(value) {
  return /[\u4e00-\u9fff]/.test(String(value || ''));
}

function normalizedLabelKey(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}

function labelTokens(value) {
  return normalizedLabelKey(value)
    .split('_')
    .filter((token) => token && !KOREAN_LABEL_SKIP_TOKENS.has(token));
}

function longestCharacterToken(tokens) {
  let best = '';
  for (let start = 0; start < tokens.length; start += 1) {
    for (let end = tokens.length; end > start; end -= 1) {
      const candidate = tokens.slice(start, end).join('_');
      if (KOREAN_CHARACTER_TOKEN_MAP[candidate] && candidate.length > best.length) {
        best = candidate;
      }
    }
  }
  return best;
}

function koreanCharacterLabelFromText(value) {
  const text = String(value || '');
  const sheet = sheetHeroInfoFor(text) || sheetHeroInfoFor(slugFromKey(text));
  if (sheet?.kr) return sheet.kr;
  const tokens = labelTokens(text);
  const joined = longestCharacterToken(tokens);
  return joined ? KOREAN_CHARACTER_TOKEN_MAP[joined] : '';
}

function translateTokenSequence(tokens) {
  const result = [];
  for (let index = 0; index < tokens.length;) {
    let matched = '';
    let matchedLabel = '';
    for (let end = tokens.length; end > index; end -= 1) {
      const candidate = tokens.slice(index, end).join('_');
      if (KOREAN_CHARACTER_TOKEN_MAP[candidate]) {
        matched = candidate;
        matchedLabel = KOREAN_CHARACTER_TOKEN_MAP[candidate];
        break;
      }
      const manualSkill = MANUAL_SKILL_EFFECTS.find((item) => item.aliases?.some((alias) => normalizedLabelKey(alias) === candidate));
      if (manualSkill) {
        matched = candidate;
        matchedLabel = manualSkill.name;
        break;
      }
    }
    if (matched) {
      result.push(matchedLabel);
      index += matched.split('_').length;
      continue;
    }
    const token = tokens[index];
    const label = KOREAN_LABEL_TOKEN_MAP[token] || KOREAN_SYLLABLE_TOKEN_MAP[token] || (/^\d+$/.test(token) ? token : '');
    if (label && result[result.length - 1] !== label) result.push(label);
    index += 1;
  }
  return result.join(' ').trim();
}

function koreanLabelFromText(value, fallback = '') {
  const text = String(value || '').trim();
  if (text && hasHangul(text)) return text;
  const fallbackText = String(fallback || '').trim();
  const source = [text, fallbackText].filter(Boolean).join(' ');
  if (!source) return '';
  const generic = genericDisplayName(source);
  if (generic) return generic;
  const person = koreanCharacterLabelFromText(source);
  if (person) {
    const normalized = normalizedLabelKey(source);
    if (normalized.includes('model') || normalized.includes('uniform')) return `${person} 모델`;
    if (normalized.includes('art') || normalized.includes('image')) return `${person} 이미지 세트`;
    if (normalized.includes('skill')) return `${person} 스킬셋`;
    if (normalized.includes('age')) return `${person} 연령대`;
    if (normalized.includes('ceo') || normalized.includes('title')) return `${person} 칭호`;
    return person;
  }
  const translated = translateTokenSequence(labelTokens(source));
  if (translated) return translated;
  if (hasCjk(text) && fallbackText) return koreanLabelFromText(fallbackText);
  return '';
}
