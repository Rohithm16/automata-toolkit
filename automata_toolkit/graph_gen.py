def generate_nfa_dot(nfa):
    lines = ['digraph NFA {', '  rankdir=LR;', '  node [shape=circle];']
    for state in nfa.states:
        if state in nfa.final_states:
            lines.append(f'  "{state}" [shape=doublecircle];')
        else:
            lines.append(f'  "{state}";')
    lines.append(f'  start [shape=none, label=""];')
    lines.append(f'  start -> "{nfa.start_state}";')
    for src, trans in nfa.transitions.items():
        for symbol, dst_set in trans.items():
            for dst in dst_set:
                label = symbol if symbol != 'ε' else 'ε'
                lines.append(f'  "{src}" -> "{dst}" [label="{label}"];')
    lines.append('}')
    return '\n'.join(lines)

def generate_dfa_dot(dfa):
    lines = ['digraph DFA {', '  rankdir=LR;', '  node [shape=circle];']
    for state in dfa.states:
        if state in dfa.final_states:
            lines.append(f'  "{state}" [shape=doublecircle];')
        else:
            lines.append(f'  "{state}";')
    lines.append(f'  start [shape=none, label=""];')
    lines.append(f'  start -> "{dfa.start_state}";')
    for src, trans in dfa.transitions.items():
        for symbol, dst in trans.items():
            lines.append(f'  "{src}" -> "{dst}" [label="{symbol}"];')
    lines.append('}')
    return '\n'.join(lines)