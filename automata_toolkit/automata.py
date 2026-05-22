from collections import deque


REGEX_OPERATORS = {'|', '.', '*', '+', '?'}


def _is_regex_symbol(token):
    return token not in REGEX_OPERATORS and token not in {'(', ')'}


def _insert_concat_operators(regex):
    tokens = [ch for ch in regex if not ch.isspace()]
    if not tokens:
        raise ValueError('Regex cannot be empty')

    output = []
    for i, token in enumerate(tokens):
        output.append(token)
        if i == len(tokens) - 1:
            continue
        nxt = tokens[i + 1]
        left_is_concat_ready = _is_regex_symbol(token) or token in {')', '*', '+', '?'}
        right_is_concat_ready = _is_regex_symbol(nxt) or nxt == '('
        if left_is_concat_ready and right_is_concat_ready:
            output.append('.')
    return output


def _regex_to_postfix(regex):
    tokens = _insert_concat_operators(regex)
    output = []
    op_stack = []
    precedence = {'|': 1, '.': 2, '*': 3, '+': 3, '?': 3}

    for token in tokens:
        if _is_regex_symbol(token):
            output.append(token)
        elif token == '(':
            op_stack.append(token)
        elif token == ')':
            while op_stack and op_stack[-1] != '(':
                output.append(op_stack.pop())
            if not op_stack:
                raise ValueError('Mismatched parentheses in regex')
            op_stack.pop()
        elif token in precedence:
            while (
                op_stack
                and op_stack[-1] != '('
                and precedence.get(op_stack[-1], 0) >= precedence[token]
            ):
                output.append(op_stack.pop())
            op_stack.append(token)
        else:
            raise ValueError(f'Unsupported token in regex: {token}')

    while op_stack:
        op = op_stack.pop()
        if op == '(':
            raise ValueError('Mismatched parentheses in regex')
        output.append(op)
    return output


def regex_to_nfa(regex, alphabet=None):
    postfix = _regex_to_postfix(regex)
    regex_symbols = {token for token in postfix if _is_regex_symbol(token) and token != 'ε'}

    if alphabet is None:
        alphabet_symbols = sorted(regex_symbols)
    else:
        alphabet_symbols = sorted({a.strip() for a in alphabet if a.strip()})
        for symbol in alphabet_symbols:
            if symbol in REGEX_OPERATORS or symbol in {'(', ')'}:
                raise ValueError(f"Invalid alphabet symbol '{symbol}'")
        missing = regex_symbols - set(alphabet_symbols)
        if missing:
            raise ValueError(
                f"Regex uses symbols not in alphabet: {', '.join(sorted(missing))}"
            )

    state_counter = 0

    def new_state():
        nonlocal state_counter
        name = f'r{state_counter}'
        state_counter += 1
        return name

    transitions = []
    states = set()
    stack = []

    for token in postfix:
        if _is_regex_symbol(token):
            start = new_state()
            end = new_state()
            symbol = token
            transitions.append(f'{start}:{symbol}->{end}')
            states.update({start, end})
            stack.append((start, end))
        elif token == '.':
            if len(stack) < 2:
                raise ValueError('Malformed regex near concatenation')
            right = stack.pop()
            left = stack.pop()
            transitions.append(f'{left[1]}:ε->{right[0]}')
            stack.append((left[0], right[1]))
        elif token == '|':
            if len(stack) < 2:
                raise ValueError('Malformed regex near union')
            right = stack.pop()
            left = stack.pop()
            start = new_state()
            end = new_state()
            transitions.extend([
                f'{start}:ε->{left[0]}',
                f'{start}:ε->{right[0]}',
                f'{left[1]}:ε->{end}',
                f'{right[1]}:ε->{end}'
            ])
            states.update({start, end})
            stack.append((start, end))
        elif token == '*':
            if not stack:
                raise ValueError('Malformed regex near Kleene star')
            inner = stack.pop()
            start = new_state()
            end = new_state()
            transitions.extend([
                f'{start}:ε->{inner[0]}',
                f'{start}:ε->{end}',
                f'{inner[1]}:ε->{inner[0]}',
                f'{inner[1]}:ε->{end}'
            ])
            states.update({start, end})
            stack.append((start, end))
        elif token == '+':
            if not stack:
                raise ValueError('Malformed regex near plus operator')
            inner = stack.pop()
            start = new_state()
            end = new_state()
            transitions.extend([
                f'{start}:ε->{inner[0]}',
                f'{inner[1]}:ε->{inner[0]}',
                f'{inner[1]}:ε->{end}'
            ])
            states.update({start, end})
            stack.append((start, end))
        elif token == '?':
            if not stack:
                raise ValueError('Malformed regex near optional operator')
            inner = stack.pop()
            start = new_state()
            end = new_state()
            transitions.extend([
                f'{start}:ε->{inner[0]}',
                f'{start}:ε->{end}',
                f'{inner[1]}:ε->{end}'
            ])
            states.update({start, end})
            stack.append((start, end))
        else:
            raise ValueError(f'Unsupported regex operator: {token}')

    if len(stack) != 1:
        raise ValueError('Malformed regex expression')

    start_state, final_state = stack.pop()
    return NFA(sorted(states), alphabet_symbols, transitions, start_state, [final_state])

class NFA:
    def __init__(self, states, alphabet, transitions, start_state, final_states):
        self.states = set(states)
        self.alphabet = set(alphabet)
        self.start_state = start_state
        self.final_states = set(final_states)
        self.transitions = {}
        for state in states:
            self.transitions[state] = {}
        for t in transitions:
            parts = t.split(':')
            src = parts[0].strip()
            rest = parts[1].split('->')
            symbol = rest[0].strip()
            dst = rest[1].strip()
            if symbol not in self.transitions[src]:
                self.transitions[src][symbol] = set()
            self.transitions[src][symbol].add(dst)

    def epsilon_closure(self, states_set):
        closure = set(states_set)
        stack = list(states_set)
        while stack:
            state = stack.pop()
            if 'ε' in self.transitions.get(state, {}):
                for next_state in self.transitions[state]['ε']:
                    if next_state not in closure:
                        closure.add(next_state)
                        stack.append(next_state)
        return closure

class DFA:
    def __init__(self, states, alphabet, transitions, start_state, final_states):
        self.states = set(states)
        self.alphabet = set(alphabet)
        self.start_state = start_state
        self.final_states = set(final_states)
        self.transitions = {}
        for state in states:
            self.transitions[state] = {}
        for t in transitions:
            parts = t.split(':')
            src = parts[0].strip()
            rest = parts[1].split('->')
            symbol = rest[0].strip()
            dst = rest[1].strip()
            self.transitions[src][symbol] = dst

def nfa_to_dfa(nfa):
    initial_state_set = frozenset(nfa.epsilon_closure({nfa.start_state}))
    dfa_alphabet = sorted(sym for sym in nfa.alphabet if sym != 'ε')
    dfa_states = []
    dfa_transitions = []
    unmarked = deque([initial_state_set])
    dfa_state_map = {initial_state_set: 'q0'}
    state_counter = 1

    while unmarked:
        current_set = unmarked.popleft()
        current_name = dfa_state_map[current_set]
        dfa_states.append(current_name)

        for symbol in dfa_alphabet:
            next_set = set()
            for nfa_state in current_set:
                if symbol in nfa.transitions.get(nfa_state, {}):
                    next_set.update(nfa.transitions[nfa_state][symbol])
            next_set = nfa.epsilon_closure(next_set)

            next_frozen = frozenset(next_set)
            if next_frozen not in dfa_state_map:
                dfa_state_map[next_frozen] = f'q{state_counter}'
                state_counter += 1
                unmarked.append(next_frozen)

            target_name = dfa_state_map[next_frozen]
            dfa_transitions.append(f"{current_name}:{symbol}->{target_name}")

    dfa_final_states = [name for nfa_set, name in dfa_state_map.items()
                        if not nfa_set.isdisjoint(nfa.final_states)]

    return DFA(dfa_states, dfa_alphabet, dfa_transitions,
               dfa_state_map[initial_state_set], dfa_final_states), dfa_state_map