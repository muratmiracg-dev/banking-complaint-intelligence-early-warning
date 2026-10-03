/* Portable TF-IDF + multinomial logistic inference. No network or external runtime. */
(function (root) {
  'use strict';
  function clean(text) {
    return String(text || '').toLowerCase().replace(/https?:\/\/\S+|www\.\S+/g, ' ')
      .replace(/\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b/g, ' ').replace(/\bx{2,}\b/g, ' ')
      .replace(/\d+/g, ' ').replace(/\s+/g, ' ').trim();
  }
  function classify(model, text) {
    const tokens = clean(text).match(/[\p{L}\p{N}_]{2,}/gu) || [];
    if (tokens.length < 5) throw new Error('Enter at least five words of an English complaint.');
    const terms = tokens.concat(tokens.slice(0, -1).map((token, i) => token + ' ' + tokens[i + 1]));
    const counts = new Map();
    terms.forEach(t => counts.set(t, (counts.get(t) || 0) + 1));
    const weights = [];
    counts.forEach((n, term) => {
      if (Object.prototype.hasOwnProperty.call(model.vocabulary, term)) {
        const index = model.vocabulary[term];
        weights.push({index, term, weight: (1 + Math.log(n)) * model.idf[index]});
      }
    });
    const norm = Math.sqrt(weights.reduce((sum, x) => sum + x.weight * x.weight, 0));
    if (!norm) throw new Error('No recognized vocabulary. This English model needs human review.');
    weights.forEach(x => x.weight /= norm);
    const result = {};
    Object.entries(model.models).forEach(([target, m]) => {
      const logits = m.coef.map((coef, j) => m.intercept[j] + weights.reduce((sum, x) => sum + coef[x.index] * x.weight, 0));
      const max = Math.max(...logits), exp = logits.map(x => Math.exp(x - max));
      const sum = exp.reduce((a, b) => a + b, 0), probs = exp.map(x => x / sum);
      const winner = probs.indexOf(Math.max(...probs));
      result[target] = {label: m.classes[winner], confidence: probs[winner], review: probs[winner] < m.threshold,
        top_terms: weights.map(x => ({term: x.term, contribution: m.coef[winner][x.index] * x.weight}))
          .filter(x => x.contribution > 0).sort((a, b) => b.contribution - a.contribution).slice(0, 8),
        alternatives: m.classes.map((label, i) => ({label, score: probs[i]})).sort((a, b) => b.score - a.score).slice(0, 3)};
    });
    return result;
  }
  root.ComplaintModel = {clean, classify};
  if (typeof module !== 'undefined') module.exports = {clean, classify};
})(typeof window !== 'undefined' ? window : globalThis);
