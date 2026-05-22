document.addEventListener('DOMContentLoaded', () => {
    function get(id) {
        return document.getElementById(id);
    }

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function setStatus(el, message, kind) {
        if (!el) {
            return;
        }
        el.className = 'status';
        if (kind) {
            el.classList.add(kind);
        }
        el.textContent = message;
    }

    function setButtonBusy(btn, busy, label) {
        if (!btn) {
            return;
        }
        if (busy) {
            btn.dataset.label = btn.textContent;
            btn.textContent = label;
            btn.disabled = true;
            return;
        }
        btn.disabled = false;
        if (btn.dataset.label) {
            btn.textContent = btn.dataset.label;
            delete btn.dataset.label;
        }
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || `Request failed (${response.status})`);
        }
        return data;
    }

    function validateCore(data) {
        if (!data.transitions || !data.transitions.trim()) {
            return 'Transitions are required.';
        }
        return null;
    }

    function renderList(list) {
        if (!list || !list.length) {
            return '<p>No data.</p>';
        }
        return `<pre>${escapeHtml(list.join('\n'))}</pre>`;
    }

    function splitLines(value) {
        return String(value || '')
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean);
    }

    function parseTransitionLines(lines) {
        const states = new Set();
        const alphabet = new Set();

        (lines || []).forEach((line) => {
            const raw = String(line || '').trim();
            if (!raw) {
                return;
            }
            const match = raw.match(/^([^:]+):(.+)->(.+)$/);
            if (!match) {
                return;
            }
            const from = match[1].trim();
            const symbol = match[2].trim();
            const to = match[3].trim();
            if (from) {
                states.add(from);
            }
            if (to) {
                states.add(to);
            }
            if (symbol && symbol !== 'ε') {
                alphabet.add(symbol);
            }
        });

        return {
            states: Array.from(states).sort(),
            alphabet: Array.from(alphabet).sort()
        };
    }

    function normalizeCsv(value) {
        return String(value || '')
            .split(',')
            .map((part) => part.trim())
            .filter(Boolean);
    }

    async function renderDotGraph(targetEl, payload) {
        if (!targetEl) {
            return;
        }

        targetEl.innerHTML = '<p>Rendering graph...</p>';
        const response = await postJson('/graph', payload);
        const viz = (typeof Module !== 'undefined' && typeof render !== 'undefined')
            ? new Viz({ Module, render })
            : new Viz();
        const element = await viz.renderSVGElement(response.dot);
        targetEl.innerHTML = '';
        targetEl.appendChild(element);
    }

    function renderSummaryBlock(title, type, states, alphabet, start, finalStates, transitions) {
        let html = '<div class="result-block">';
        html += `<h3>${escapeHtml(title)}</h3>`;
        html += `<p><strong>Type:</strong> ${escapeHtml(type)}</p>`;
        html += `<p><strong>States:</strong> ${escapeHtml((states || []).join(', ') || '(none)')}</p>`;
        html += `<p><strong>Alphabet:</strong> ${escapeHtml((alphabet || []).join(', ') || '(none)')}</p>`;
        html += `<p><strong>Start State:</strong> ${escapeHtml(start || '(none)')}</p>`;
        html += `<p><strong>Final States:</strong> ${escapeHtml((finalStates || []).join(', ') || '(none)')}</p>`;
        html += '<h4>Transitions</h4>';
        html += renderList(transitions || []);
        html += '</div>';
        return html;
    }

    function renderMappingBlock(mapping) {
        let html = '<div class="result-block">';
        html += '<h3>Subset Mapping</h3>';
        html += '<ul>';
        Object.entries(mapping || {})
            .sort((a, b) => a[0].localeCompare(b[0]))
            .forEach(([name, subset]) => {
                html += `<li>${escapeHtml(name)} = {${escapeHtml(subset)}}</li>`;
            });
        html += '</ul>';
        html += '</div>';
        return html;
    }

    function renderGraphBlock(id, title) {
        return `<div class="result-block"><h3>${escapeHtml(title)}</h3><div id="${escapeHtml(id)}" class="graph-output"></div></div>`;
    }

    function ensureGraphOutput(container, id, title) {
        let node = get(id);
        if (node) {
            return node;
        }
        if (container) {
            container.innerHTML += renderGraphBlock(id, title);
            node = get(id);
        }
        return node;
    }

    function clearOutput(statusEl, resultEl) {
        if (resultEl) {
            resultEl.innerHTML = '';
        }
        setStatus(statusEl, 'Ready', null);
    }

    function setupSimulationPage() {
        const form = get('simulate-form');
        if (!form) {
            return;
        }

        const btn = get('simulate-btn');
        const exampleBtn = get('sim-example-btn');
        const clearBtn = get('sim-clear-btn');
        const status = get('simulate-status');
        const result = get('simulate-result');

        function loadSimulationExample() {
            get('sim-transitions').value = [
                's0:a->s1',
                's0:b->s0',
                's1:a->s1',
                's1:b->s2',
                's2:a->s1',
                's2:b->s0'
            ].join('\n');
            get('sim-start').value = 's0';
            get('sim-final').value = 's2';
            setStatus(status, 'Example loaded.', null);
        }

        if (exampleBtn) {
            exampleBtn.addEventListener('click', loadSimulationExample);
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                clearOutput(status, result);
            });
        }

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const data = {
                type: 'dfa',
                transitions: get('sim-transitions').value,
                start: get('sim-start').value,
                final: get('sim-final').value
            };

            const error = validateCore(data);
            if (error) {
                setStatus(status, error, 'warn');
                return;
            }

            setButtonBusy(btn, true, 'Building...');
            setStatus(status, 'Building DFA...', null);
            try {
                const transitions = splitLines(data.transitions);
                const parsed = parseTransitionLines(transitions);
                const finals = normalizeCsv(data.final);

                let html = renderSummaryBlock(
                    'DFA Details',
                    'DFA',
                    parsed.states,
                    parsed.alphabet,
                    data.start,
                    finals,
                    transitions
                );
                html += renderGraphBlock('dfa-graph-output', 'DFA Graph');
                result.innerHTML = html;

                await renderDotGraph(get('dfa-graph-output'), data);
                setStatus(status, 'Done.', 'ok');
            } catch (err) {
                result.innerHTML = `<p>${escapeHtml(err.message)}</p>`;
                setStatus(status, 'Failed.', 'err');
            } finally {
                setButtonBusy(btn, false);
            }
        });
    }

    function setupConvertPage() {
        const form = get('convert-form');
        if (!form) {
            return;
        }

        const btn = get('convert-btn');
        const exampleBtn = get('conv-example-btn');
        const clearBtn = get('conv-clear-btn');
        const graphNfaBtn = get('conv-graph-nfa-btn');
        const graphDfaBtn = get('conv-graph-dfa-btn');
        const status = get('convert-status');
        const result = get('convert-result');
        let latestConvertedDfa = null;

        function loadConvertExample() {
            get('conv-transitions').value = [
                'n0:ε->n1',
                'n0:ε->n3',
                'n1:a->n2',
                'n2:b->n2',
                'n2:ε->n4',
                'n3:b->n4',
                'n4:a->n4'
            ].join('\n');
            get('conv-start').value = 'n0';
            get('conv-final').value = 'n4';
            setStatus(status, 'Example loaded.', null);
            if (graphDfaBtn) {
                graphDfaBtn.classList.add('is-hidden');
            }
            latestConvertedDfa = null;
        }

        if (exampleBtn) {
            exampleBtn.addEventListener('click', loadConvertExample);
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                latestConvertedDfa = null;
                if (graphDfaBtn) {
                    graphDfaBtn.classList.add('is-hidden');
                }
                clearOutput(status, result);
            });
        }

        if (graphNfaBtn) {
            graphNfaBtn.addEventListener('click', async () => {
                const payload = {
                    type: 'nfa',
                    transitions: get('conv-transitions').value,
                    start: get('conv-start').value,
                    final: get('conv-final').value
                };
                const error = validateCore(payload);
                if (error) {
                    setStatus(status, error, 'warn');
                    return;
                }

                setButtonBusy(graphNfaBtn, true, 'Graphing...');
                setStatus(status, 'Rendering NFA graph...', null);
                try {
                    const transitions = splitLines(payload.transitions);
                    const parsed = parseTransitionLines(transitions);
                    const finals = normalizeCsv(payload.final);
                    if (!result.innerHTML.trim()) {
                        result.innerHTML = renderSummaryBlock(
                            'NFA Details',
                            'NFA',
                            parsed.states,
                            parsed.alphabet,
                            payload.start,
                            finals,
                            transitions
                        );
                    }
                    const graphOutput = ensureGraphOutput(result, 'convert-graph-output', 'Graph');
                    await renderDotGraph(graphOutput, payload);
                    setStatus(status, 'Done.', 'ok');
                } catch (err) {
                    setStatus(status, 'Failed.', 'err');
                } finally {
                    setButtonBusy(graphNfaBtn, false);
                }
            });
        }

        if (graphDfaBtn) {
            graphDfaBtn.addEventListener('click', async () => {
                if (!latestConvertedDfa) {
                    setStatus(status, 'Convert to DFA first to graph the converted automaton.', 'warn');
                    return;
                }
                setButtonBusy(graphDfaBtn, true, 'Graphing...');
                setStatus(status, 'Rendering converted DFA graph...', null);
                try {
                    const graphOutput = ensureGraphOutput(result, 'convert-graph-output', 'Graph');
                    await renderDotGraph(graphOutput, latestConvertedDfa);
                    setStatus(status, 'Done.', 'ok');
                } catch (err) {
                    setStatus(status, 'Failed.', 'err');
                } finally {
                    setButtonBusy(graphDfaBtn, false);
                }
            });
        }

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const payload = {
                transitions: get('conv-transitions').value,
                start: get('conv-start').value,
                final: get('conv-final').value
            };

            const error = validateCore(payload);
            if (error) {
                setStatus(status, error, 'warn');
                return;
            }

            setButtonBusy(btn, true, 'Converting...');
            setStatus(status, 'Converting...', null);
            try {
                const converted = await postJson('/convert', payload);
                const nfaTransitions = splitLines(payload.transitions);
                const nfaSummary = parseTransitionLines(nfaTransitions);
                const nfaFinals = normalizeCsv(payload.final);

                let html = renderSummaryBlock(
                    'NFA Details',
                    'NFA',
                    nfaSummary.states,
                    nfaSummary.alphabet,
                    payload.start,
                    nfaFinals,
                    nfaTransitions
                );
                html += renderSummaryBlock(
                    'Converted DFA Details',
                    'DFA',
                    converted.dfa_states,
                    converted.dfa_alphabet,
                    converted.dfa_start,
                    converted.dfa_final,
                    converted.dfa_transitions
                );
                html += renderMappingBlock(converted.mapping);
                html += renderGraphBlock('convert-graph-output', 'Graph');
                result.innerHTML = html;

                latestConvertedDfa = {
                    type: 'dfa',
                    transitions: converted.dfa_transitions.join('\n'),
                    start: converted.dfa_start,
                    final: converted.dfa_final.join(',')
                };
                if (graphDfaBtn) {
                    graphDfaBtn.classList.remove('is-hidden');
                }
                setStatus(status, 'Done.', 'ok');
            } catch (err) {
                latestConvertedDfa = null;
                if (graphDfaBtn) {
                    graphDfaBtn.classList.add('is-hidden');
                }
                result.innerHTML = `<p>${escapeHtml(err.message)}</p>`;
                setStatus(status, 'Failed.', 'err');
            } finally {
                setButtonBusy(btn, false);
            }
        });
    }

    function setupRegexPage() {
        const form = get('regex-form');
        const targetSwitch = get('regex-target-switch');
        const pageStatus = get('regex-page-status');
        if (!form || !targetSwitch || !pageStatus) {
            return;
        }

        const btn = get('regex-btn');
        const exampleBtn = get('regex-example-btn');
        const clearBtn = get('regex-clear-btn');
        const status = get('regex-status');
        const result = get('regex-result');

        const targets = ['nfa', 'dfa'];
        const params = new URLSearchParams(window.location.search);
        let target = params.get('target');
        if (!targets.includes(target)) {
            target = 'nfa';
        }

        const targetButtons = Array.from(targetSwitch.querySelectorAll('[data-target]'));

        function syncTarget() {
            targetButtons.forEach((button) => {
                button.classList.toggle('active', button.dataset.target === target);
            });
            params.set('target', target);
            const nextUrl = `${window.location.pathname}?${params.toString()}`;
            window.history.replaceState({}, '', nextUrl);
            if (target === 'nfa') {
                setStatus(pageStatus, 'Target: NFA', null);
            } else {
                setStatus(pageStatus, 'Target: DFA', null);
            }
        }

        targetButtons.forEach((button) => {
            button.addEventListener('click', () => {
                target = button.dataset.target;
                syncTarget();
            });
        });

        if (exampleBtn) {
            exampleBtn.addEventListener('click', () => {
                get('regex-value').value = '(a|b)*abb(a|b)';
                setStatus(status, 'Example loaded.', null);
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                clearOutput(status, result);
            });
        }

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const regex = get('regex-value').value.trim();
            if (!regex) {
                setStatus(status, 'Regex is required.', 'warn');
                return;
            }

            setButtonBusy(btn, true, 'Converting...');
            setStatus(status, 'Converting regex...', null);
            try {
                const response = await postJson('/regex_convert', { regex });
                let html = '<div class="result-block">';
                html += '<h3>Regex Input</h3>';
                html += `<p><strong>Expression:</strong> ${escapeHtml(response.regex)}</p>`;
                html += '</div>';

                if (target === 'nfa') {
                    html += renderSummaryBlock(
                        'NFA Details',
                        'NFA',
                        response.nfa.states,
                        response.nfa.alphabet,
                        response.nfa.start,
                        response.nfa.final,
                        response.nfa.transitions
                    );
                } else {
                    html += renderSummaryBlock(
                        'DFA Details',
                        'DFA',
                        response.dfa.states,
                        response.dfa.alphabet,
                        response.dfa.start,
                        response.dfa.final,
                        response.dfa.transitions
                    );
                    html += renderMappingBlock(response.subset_map);
                }

                result.innerHTML = html;
                setStatus(status, 'Done.', 'ok');
            } catch (err) {
                result.innerHTML = `<p>${escapeHtml(err.message)}</p>`;
                setStatus(status, 'Failed.', 'err');
            } finally {
                setButtonBusy(btn, false);
            }
        });

        syncTarget();
    }

    setupSimulationPage();
    setupConvertPage();
    setupRegexPage();
});
