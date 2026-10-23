# InvenioLang curriculum (en)

*[Versión en español](README.md)*

A progressive curriculum of **13 levels and 133 exercises** covering
Programming I, arrays and matrices, strings, Programming II (OOP and design
patterns), data structures (stacks, queues, lists, trees, heaps, hash tables
and graphs) and algorithmic complexity. Every exercise exists **twice**: with
Spanish keywords (`es/nivelNN/`) and with English keywords (`en/levelNN/`).
Both versions produce exactly the same output.

## Layout

```
curriculum/
  runner.py                 runner and checker (both languages)
  es/nivel01 … es/nivel13   version with Spanish keywords
  en/level01 … en/level13   version with English keywords
    nivel.json              level title, description and topics
    NN_name.inv             commented reference solution
    NN_name.expected        exact expected output
    NN_name.json            id, title, statement, goals, graded hints, concepts
    NN_name.entrada         (optional) one line per read
```

Pairs are matched by the JSON `id` (`N04-E05` is exercise 5 of level 4 in both
languages). The statement, goals and hints are written in the folder's
language; the text the programs print is the same in both versions (hence
neutral labels such as `sum =`, `max =` or `BFS:`), so a single `.expected`
checks both. The metadata keys (`titulo`, `enunciado`, `objetivos`, `pistas`,
`conceptos`) are the same in both languages because the tooling is written in
Spanish.

Each `.inv` starts with a title and goals header and is commented to explain
*why* each step is taken. **Hints are graded**: the first one points you in a
direction, the second gets close to the key idea and the third almost gives
the solution away.

## Run and check

```bash
python curriculum/runner.py                       # whole curriculum, both versions
python curriculum/runner.py 4 level5              # levels 4 and 5 only
python curriculum/runner.py --version en          # English-keyword version only
python curriculum/runner.py --idioma en           # messages, statements and hints in English
python curriculum/runner.py --ejercicio N04-E05 --enunciado --pistas 3 --idioma en
```

The runner compares the **exact** output (it only tolerates `\r\n` and
trailing line breaks), checks that the `es` and `en` versions print the same,
shows the statement, goals and requested hints when something fails, and exits
with 0 when everything passes, 1 when something fails and 2 when there is
nothing to run. Exercises that use `read` get their `.entrada` file; the runner
never waits for the keyboard. `tests/test_curriculum.py` runs the WHOLE
curriculum in both languages and validates its structure; the CI "Curriculum"
step runs the runner.

## Adding an exercise

1. Write `es/nivelNN/MM_name.inv` and its `.expected` (and `.entrada` if it reads input).
2. Write the English version `en/levelNN/MM_name.inv` with the same statements,
   English identifiers and comments, and **the same output**.
3. Create both `.json` files with the same `id` (`NNN-EMM`), each in its own
   language, with at least three graded hints.
4. Run `python curriculum/runner.py NN` and `pytest tests/test_curriculum.py`.

## Constructs the curriculum avoids (and why)

- Member access is single-level: `a.next.value` is not valid; use
  `Node n = a.next; n.value` (see `docs/InvenioLang_2.0_POO.md` §8).
- Classes have no array attributes: array-based stacks/queues and hash tables
  use global arrays or arrays passed as parameters.
- `read` only accepts a variable (not `read(a[i])`), `a[i]++` does not exist and
  a call cannot be chained onto `new C()`.
- Parameters cannot have function types: the pluggable comparator (N05-E09)
  uses a global function-typed variable.
- Interpreter defects pending a fix in the core: `i += 2` in a `for` update
  assigns instead of adding; a local declared inside a block with the same name
  as a global overwrites the global; and a function reading a global sees its
  caller's local with the same name. The exercises use `i = i + 2` and avoid
  shadowing globals from `main`.

## Curriculum map
### Level 1 — Fundamentals: variables, types, operators and I/O

First programs: display data, store values in variables, compute with them and read user input.

**Topics:** output with print; variables and constants; int, float, string and bool types; arithmetic, relational and logical operators; input with read; type conversions.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N01-E01 | Hello, world | [`01_hello_world.inv`](en/level01/01_hello_world.inv) | program, main, output |
| N01-E02 | Variables and assignment | [`02_variables.inv`](en/level01/02_variables.inv) | variable, assignment, swap |
| N01-E03 | Data types | [`03_data_types.inv`](en/level01/03_data_types.inv) | int, float, string, bool |
| N01-E04 | Constants | [`04_constants.inv`](en/level01/04_constants.inv) | constant, expression |
| N01-E05 | Arithmetic operators | [`05_arithmetic_operators.inv`](en/level01/05_arithmetic_operators.inv) | integer division, modulo, real division |
| N01-E06 | Operator precedence | [`06_precedence.inv`](en/level01/06_precedence.inv) | precedence, associativity, parentheses |
| N01-E07 | Relational and logical operators | [`07_relational_and_logical.inv`](en/level01/07_relational_and_logical.inv) | comparison, conjunction, disjunction, negation |
| N01-E08 | Reading input | [`08_reading_input.inv`](en/level01/08_reading_input.inv) | input, read |
| N01-E09 | Type conversion | [`09_conversions.inv`](en/level01/09_conversions.inv) | conversion, truncation, concatenation |
| N01-E10 | Basic strings | [`10_basic_strings.inv`](en/level01/10_basic_strings.inv) | string, index, substring |
| N01-E11 | Increment and compound assignment | [`11_increment_and_compound_assignment.inv`](en/level01/11_increment_and_compound_assignment.inv) | increment, compound assignment |
| N01-E12 | Temperature converter | [`12_temperature_converter.inv`](en/level01/12_temperature_converter.inv) | input-process-output, formula |

### Level 2 — Control flow: decisions and loops

Structured programming: choose between paths (if, switch, ternary) and repeat (while, do-while, for, foreach).

**Topics:** if / else and else-if chains; switch / case; ternary operator; while, do-while, for; break and continue; nested loops; accumulators and counters.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N02-E01 | Even or odd | [`01_even_or_odd.inv`](en/level02/01_even_or_odd.inv) | conditional, if/else, modulo |
| N02-E02 | Grade with else-if | [`02_grade_with_else_if.inv`](en/level02/02_grade_with_else_if.inv) | else-if, mutually exclusive conditions |
| N02-E03 | Multiple selection with switch | [`03_switch_case.inv`](en/level02/03_switch_case.inv) | switch, fall-through, break |
| N02-E04 | Ternary operator | [`04_ternary_operator.inv`](en/level02/04_ternary_operator.inv) | ternary, conditional expression |
| N02-E05 | While loop | [`05_while_loop.inv`](en/level02/05_while_loop.inv) | while, stop condition, counter |
| N02-E06 | do-while: validating input | [`06_do_while_validation.inv`](en/level02/06_do_while_validation.inv) | do-while, validation |
| N02-E07 | For loop: multiplication table | [`07_for_loop_table.inv`](en/level02/07_for_loop_table.inv) | for, loop variable |
| N02-E08 | Nested loops: shapes | [`08_nested_loops.inv`](en/level02/08_nested_loops.inv) | nested loops, patterns |
| N02-E09 | break and continue | [`09_break_and_continue.inv`](en/level02/09_break_and_continue.inv) | break, continue |
| N02-E10 | Accumulators and counters | [`10_accumulators_and_counters.inv`](en/level02/10_accumulators_and_counters.inv) | accumulator, counter, maximum |
| N02-E11 | Digits of a number | [`11_digits_of_a_number.inv`](en/level02/11_digits_of_a_number.inv) | digit decomposition, while |
| N02-E12 | Prime numbers | [`12_prime_numbers.inv`](en/level02/12_prime_numbers.inv) | flag, nested loops, primality |
| N02-E13 | Iterating with foreach | [`13_foreach.inv`](en/level02/13_foreach.inv) | foreach, traversal |

### Level 3 — Functions, procedures and recursion

Break a problem into reusable subprograms, pass parameters and solve problems defined in terms of themselves.

**Topics:** functions with return values; procedures (void); pass by value and by reference (arrays); variable scope; recursion: base case and recursive case; functions as values.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N03-E01 | Functions with return values | [`01_functions.inv`](en/level03/01_functions.inv) | function, parameter, return |
| N03-E02 | Procedures | [`02_procedures.inv`](en/level03/02_procedures.inv) | procedure, reuse |
| N03-E03 | Pass by value and by reference | [`03_parameter_passing.inv`](en/level03/03_parameter_passing.inv) | pass by value, pass by reference |
| N03-E04 | Variable scope | [`04_variable_scope.inv`](en/level03/04_variable_scope.inv) | scope, global variable, shadowing |
| N03-E05 | Boolean functions | [`05_boolean_functions.inv`](en/level03/05_boolean_functions.inv) | boolean function, leap year |
| N03-E06 | Recursive factorial | [`06_recursive_factorial.inv`](en/level03/06_recursive_factorial.inv) | recursion, base case, call stack |
| N03-E07 | Fibonacci: recursive and iterative | [`07_fibonacci.inv`](en/level03/07_fibonacci.inv) | multiple recursion, iteration, exponential cost |
| N03-E08 | Fast exponentiation | [`08_fast_power.inv`](en/level03/08_fast_power.inv) | divide and conquer, recursion |
| N03-E09 | Greatest common divisor (Euclid) | [`09_gcd_euclid.inv`](en/level03/09_gcd_euclid.inv) | Euclid's algorithm, recursion |
| N03-E10 | Towers of Hanoi | [`10_towers_of_hanoi.inv`](en/level03/10_towers_of_hanoi.inv) | recursion, divide and conquer |
| N03-E11 | Recursion with strings and digits | [`11_recursion_with_strings.inv`](en/level03/11_recursion_with_strings.inv) | recursion, palindrome, base 2 |
| N03-E12 | Functions as values | [`12_functions_as_values.inv`](en/level03/12_functions_as_values.inv) | first-class function, higher order, lambda |

### Level 4 — Arrays and vectors: traversal and search

Store collections of same-typed data, traverse them, search them and transform them in place.

**Topics:** array declaration and initialization; traversals; maximum, minimum and averages; linear and binary search; frequency counting; in-place transformations.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N04-E01 | Declare and traverse an array | [`01_declare_and_traverse.inv`](en/level04/01_declare_and_traverse.inv) | array, index, traversal |
| N04-E02 | Sum, average and values above average | [`02_sum_and_average.inv`](en/level04/02_sum_and_average.inv) | array, accumulator, two passes |
| N04-E03 | Maximum, minimum and their positions | [`03_maximum_and_minimum.inv`](en/level04/03_maximum_and_minimum.inv) | maximum, minimum, position |
| N04-E04 | Linear search | [`04_linear_search.inv`](en/level04/04_linear_search.inv) | linear search, sentinel, O(n) |
| N04-E05 | Binary search | [`05_binary_search.inv`](en/level04/05_binary_search.inv) | binary search, divide and conquer, O(log n) |
| N04-E06 | Recursive binary search | [`06_recursive_binary_search.inv`](en/level04/06_recursive_binary_search.inv) | recursion, binary search |
| N04-E07 | Reverse in place | [`07_reverse_in_place.inv`](en/level04/07_reverse_in_place.inv) | two pointers, swap, in place |
| N04-E08 | Frequency counting | [`08_frequency_count.inv`](en/level04/08_frequency_count.inv) | counter array, histogram, mode |
| N04-E09 | Rotate an array | [`09_rotate_array.inv`](en/level04/09_rotate_array.inv) | rotation, subrange |
| N04-E10 | Remove duplicates from a sorted array | [`10_remove_duplicates.inv`](en/level04/10_remove_duplicates.inv) | logical size, two indexes |
| N04-E11 | Prefix sums | [`11_prefix_sums.inv`](en/level04/11_prefix_sums.inv) | prefix sum, precomputation |
| N04-E12 | Merge two sorted arrays | [`12_merge_sorted.inv`](en/level04/12_merge_sorted.inv) | merge, O(n + m) |

### Level 5 — Sorting algorithms

Sort data with classic algorithms (bubble, selection, insertion, merge, quick and counting sort), follow how they work step by step and compare their work.

**Topics:** bubble sort; selection sort; insertion sort; merge sort; quick sort; counting sort; stability and sort criteria.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N05-E01 | Bubble sort | [`01_bubble_sort.inv`](en/level05/01_bubble_sort.inv) | bubble sort, comparison, O(n²) |
| N05-E02 | Optimized bubble sort | [`02_optimized_bubble_sort.inv`](en/level05/02_optimized_bubble_sort.inv) | flag, best case, worst case |
| N05-E03 | Selection sort | [`03_selection_sort.inv`](en/level05/03_selection_sort.inv) | selection sort, invariant |
| N05-E04 | Insertion sort | [`04_insertion_sort.inv`](en/level05/04_insertion_sort.inv) | insertion sort, shift |
| N05-E05 | Merge sort | [`05_merge_sort.inv`](en/level05/05_merge_sort.inv) | merge sort, divide and conquer, O(n log n) |
| N05-E06 | Quick sort | [`06_quick_sort.inv`](en/level05/06_quick_sort.inv) | quick sort, pivot, partition |
| N05-E07 | Counting sort | [`07_counting_sort.inv`](en/level05/07_counting_sort.inv) | counting sort, O(n + k) |
| N05-E08 | Sorting records with parallel arrays | [`08_sorting_records.inv`](en/level05/08_sorting_records.inv) | parallel arrays, stability, descending order |
| N05-E09 | Pluggable sort criterion | [`09_sort_criterion.inv`](en/level05/09_sort_criterion.inv) | function as value, comparator |

### Level 6 — Matrices

Two-dimensional arrays: row and column traversals, linear algebra operations and table problems.

**Topics:** declaration and row/column traversal; matrix addition and product; transpose; diagonals; properties: symmetry, identity; matrices as data tables.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N06-E01 | Traversing a matrix | [`01_matrix_traversal.inv`](en/level06/01_matrix_traversal.inv) | matrix, row, column |
| N06-E02 | Sales table: row and column totals | [`02_sales_table.inv`](en/level06/02_sales_table.inv) | row totals, column totals |
| N06-E03 | Matrix addition | [`03_matrix_addition.inv`](en/level06/03_matrix_addition.inv) | matrix addition, matrix parameter |
| N06-E04 | Matrix product | [`04_matrix_product.inv`](en/level06/04_matrix_product.inv) | matrix product, dot product, O(n³) |
| N06-E05 | Transpose of a matrix | [`05_transpose.inv`](en/level06/05_transpose.inv) | transpose, in place |
| N06-E06 | Diagonals | [`06_diagonals.inv`](en/level06/06_diagonals.inv) | main diagonal, anti-diagonal, upper triangle |
| N06-E07 | Properties: symmetric and identity | [`07_matrix_properties.inv`](en/level06/07_matrix_properties.inv) | symmetric matrix, identity matrix, counterexample |
| N06-E08 | Pascal's triangle | [`08_pascals_triangle.inv`](en/level06/08_pascals_triangle.inv) | dynamic programming, binomial coefficients |
| N06-E09 | Rotate a matrix 90 degrees | [`09_rotate_matrix.inv`](en/level06/09_rotate_matrix.inv) | rotation, composition |

### Level 7 — Strings

Process text character by character: count, search, transform, encrypt and compress strings.

**Topics:** character-by-character traversal; substring search; transformations (upper case, reversal); words and separators; Caesar cipher; number-text conversion; RLE compression.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N07-E01 | Count vowels, consonants and spaces | [`01_count_characters.inv`](en/level07/01_count_characters.inv) | string traversal, classification |
| N07-E02 | Reverse and detect palindromes | [`02_palindromes.inv`](en/level07/02_palindromes.inv) | concatenation, normalization, palindrome |
| N07-E03 | Capitalize words | [`03_capitalize_words.inv`](en/level07/03_capitalize_words.inv) | state machine, words |
| N07-E04 | Substring search | [`04_substring_search.inv`](en/level07/04_substring_search.inv) | pattern search, overlap |
| N07-E05 | Caesar cipher | [`05_caesar_cipher.inv`](en/level07/05_caesar_cipher.inv) | encryption, modular arithmetic |
| N07-E06 | Converting between numbers and text | [`06_numbers_and_text.inv`](en/level07/06_numbers_and_text.inv) | base 2, Horner's scheme, conversion |
| N07-E07 | Anagrams | [`07_anagrams.inv`](en/level07/07_anagrams.inv) | anagram, counting array |
| N07-E08 | RLE compression | [`08_rle_compression.inv`](en/level07/08_rle_compression.inv) | RLE, run, compression |

### Level 8 — OOP I: classes and objects

Programming II: model entities with classes, protect their state (encapsulation), build objects in several ways and combine them.

**Topics:** classes, attributes and methods; encapsulation: public/private; constructors and overloading; toString and equals; static members; composition; arrays of objects; references and null; enumerations.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N08-E01 | My first class | [`01_first_class.inv`](en/level08/01_first_class.inv) | class, object, method, constructor |
| N08-E02 | Encapsulation: bank account | [`02_encapsulation.inv`](en/level08/02_encapsulation.inv) | encapsulation, private, invariant, getter |
| N08-E03 | Constructor overloading | [`03_constructors.inv`](en/level08/03_constructors.inv) | overloading, constructor |
| N08-E04 | Fractions: toString and immutable objects | [`04_fractions_and_tostring.inv`](en/level08/04_fractions_and_tostring.inv) | toString, immutability |
| N08-E05 | Static members | [`05_static_members.inv`](en/level08/05_static_members.inv) | static, class attribute |
| N08-E06 | Composition: a car has an engine | [`06_composition.inv`](en/level08/06_composition.inv) | composition, delegation, has-a |
| N08-E07 | Array of objects | [`07_array_of_objects.inv`](en/level08/07_array_of_objects.inv) | array of objects, traversal |
| N08-E08 | References, null and equality | [`08_references_and_equality.inv`](en/level08/08_references_and_equality.inv) | reference, aliasing, null, equality |
| N08-E09 | Enumerations | [`09_enumerations.inv`](en/level08/09_enumerations.inv) | enumeration, match, exhaustiveness |

### Level 9 — OOP II: inheritance, polymorphism and design patterns

Reuse and extend behaviour with inheritance, program against abstractions (abstract classes and interfaces) and apply classic design patterns.

**Topics:** inheritance and super; overriding and polymorphism; abstract classes; interfaces; overloading and generics; patterns: Strategy, Observer, Factory, Singleton, Template Method, Decorator; sum types and match.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N09-E01 | Inheritance | [`01_inheritance.inv`](en/level09/01_inheritance.inv) | inheritance, is-a, super |
| N09-E02 | Polymorphism | [`02_polymorphism.inv`](en/level09/02_polymorphism.inv) | polymorphism, overriding, dynamic dispatch |
| N09-E03 | Abstract classes | [`03_abstract_class.inv`](en/level09/03_abstract_class.inv) | abstract class, abstract method, contract |
| N09-E04 | Interfaces | [`04_interfaces.inv`](en/level09/04_interfaces.inv) | interface, implements, capability |
| N09-E05 | Method overloading and generics | [`05_overloading_and_generics.inv`](en/level09/05_overloading_and_generics.inv) | overloading, generics, type parameter |
| N09-E06 | Strategy pattern | [`06_strategy_pattern.inv`](en/level09/06_strategy_pattern.inv) | Strategy, composition, open/closed |
| N09-E07 | Observer pattern | [`07_observer_pattern.inv`](en/level09/07_observer_pattern.inv) | Observer, event, loose coupling |
| N09-E08 | Factory pattern | [`08_factory_pattern.inv`](en/level09/08_factory_pattern.inv) | Factory, object creation |
| N09-E09 | Singleton pattern | [`09_singleton_pattern.inv`](en/level09/09_singleton_pattern.inv) | Singleton, private constructor, lazy initialization |
| N09-E10 | Template Method pattern | [`10_template_method_pattern.inv`](en/level09/10_template_method_pattern.inv) | Template Method, hook |
| N09-E11 | Decorator pattern | [`11_decorator_pattern.inv`](en/level09/11_decorator_pattern.inv) | Decorator, wrapping, composition |
| N09-E12 | Sum types and match | [`12_sum_types.inv`](en/level09/12_sum_types.inv) | sum type, match, destructuring |

### Level 10 — Linear data structures: stacks, queues and lists

Implement stacks and queues with arrays and with linked nodes, singly and doubly linked lists, and use them to solve classic problems.

**Topics:** array-based and linked stack; circular and linked queue; singly linked list; doubly linked list; applications: brackets, postfix, Josephus.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N10-E01 | Array-based stack | [`01_array_stack.inv`](en/level10/01_array_stack.inv) | stack, LIFO, overflow |
| N10-E02 | Linked stack | [`02_linked_stack.inv`](en/level10/02_linked_stack.inv) | stack, node, linked list |
| N10-E03 | Balanced brackets | [`03_balanced_brackets.inv`](en/level10/03_balanced_brackets.inv) | stack, parsing, balancing |
| N10-E04 | Evaluating postfix expressions | [`04_postfix_evaluation.inv`](en/level10/04_postfix_evaluation.inv) | postfix notation, stack |
| N10-E05 | Circular array queue | [`05_circular_queue.inv`](en/level10/05_circular_queue.inv) | queue, FIFO, circular buffer |
| N10-E06 | Linked queue: turn simulation | [`06_linked_queue.inv`](en/level10/06_linked_queue.inv) | queue, FIFO, simulation |
| N10-E07 | Singly linked list | [`07_singly_linked_list.inv`](en/level10/07_singly_linked_list.inv) | linked list, node, link |
| N10-E08 | Doubly linked list | [`08_doubly_linked_list.inv`](en/level10/08_doubly_linked_list.inv) | doubly linked list, backward traversal |
| N10-E09 | Sorted list | [`09_sorted_list.inv`](en/level10/09_sorted_list.inv) | invariant, sorted insertion |
| N10-E10 | Josephus problem with a circular list | [`10_josephus_problem.inv`](en/level10/10_josephus_problem.inv) | circular list, simulation |

### Level 11 — Trees, heaps and hash tables

Non-linear and fast-access structures: binary search trees (insertion, traversals, height, deletion), AVL, heaps and hash tables.

**Topics:** binary search tree; pre/in/post/level-order traversals; height and recursive counts; BST deletion; AVL tree and rotations; binary heap; hash tables: linear probing and chaining.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N11-E01 | Binary search tree: insertion | [`01_bst_insertion.inv`](en/level11/01_bst_insertion.inv) | BST, recursion, in-order |
| N11-E02 | Tree traversals | [`02_bst_traversals.inv`](en/level11/02_bst_traversals.inv) | pre-order, in-order, post-order |
| N11-E03 | Search, minimum and maximum in a BST | [`03_bst_search.inv`](en/level11/03_bst_search.inv) | BST search, path, O(h) |
| N11-E04 | Height, nodes and leaves | [`04_bst_height_and_counts.inv`](en/level11/04_bst_height_and_counts.inv) | height, leaf, degenerate tree |
| N11-E05 | BST deletion | [`05_bst_deletion.inv`](en/level11/05_bst_deletion.inv) | deletion, in-order successor |
| N11-E06 | Level-order traversal (BFS on trees) | [`06_level_order_traversal.inv`](en/level11/06_level_order_traversal.inv) | level-order traversal, BFS, queue |
| N11-E07 | Min-heap (priority queue) | [`07_min_heap.inv`](en/level11/07_min_heap.inv) | heap, priority queue, O(log n) |
| N11-E08 | AVL tree: insertion with rotations | [`08_avl_tree.inv`](en/level11/08_avl_tree.inv) | AVL, rotation, balance factor |
| N11-E09 | Hash table with linear probing | [`09_hash_linear_probing.inv`](en/level11/09_hash_linear_probing.inv) | hash table, collision, linear probing |
| N11-E10 | Hash table with chaining | [`10_hash_chaining.inv`](en/level11/10_hash_chaining.inv) | chaining, dictionary, hash function |

### Level 12 — Graphs

Represent relationships with adjacency matrices and lists, traverse them (BFS, DFS) and solve classic problems: shortest paths, components, topological order and cycles.

**Topics:** adjacency matrix; adjacency list; BFS and DFS; unweighted shortest path; connected components; Dijkstra; topological sort; cycle detection.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N12-E01 | Adjacency matrix | [`01_adjacency_matrix.inv`](en/level12/01_adjacency_matrix.inv) | graph, adjacency matrix, degree |
| N12-E02 | Adjacency list | [`02_adjacency_list.inv`](en/level12/02_adjacency_list.inv) | adjacency list, sparse graph |
| N12-E03 | Breadth-first search (BFS) | [`03_bfs.inv`](en/level12/03_bfs.inv) | BFS, queue, distance |
| N12-E04 | Depth-first search (DFS) | [`04_dfs.inv`](en/level12/04_dfs.inv) | DFS, recursion, stack |
| N12-E05 | Reconstructing the shortest path | [`05_bfs_shortest_path.inv`](en/level12/05_bfs_shortest_path.inv) | predecessor, shortest path, BFS |
| N12-E06 | Connected components | [`06_connected_components.inv`](en/level12/06_connected_components.inv) | connected component, DFS |
| N12-E07 | Weighted shortest paths: Dijkstra | [`07_dijkstra.inv`](en/level12/07_dijkstra.inv) | Dijkstra, relaxation, greedy algorithm |
| N12-E08 | Topological sort (Kahn) | [`08_topological_sort.inv`](en/level12/08_topological_sort.inv) | topological sort, directed acyclic graph, in-degree |
| N12-E09 | Cycle detection in directed graphs | [`09_cycle_detection.inv`](en/level12/09_cycle_detection.inv) | cycle, back edge, DFS |

### Level 13 — Algorithmic complexity

Measure the work done by algorithms by counting operations and relate it to big-O notation: O(1), O(log n), O(n), O(n log n), O(n²) and O(2^n).

**Topics:** operation counting; orders of growth; best, worst and average case; O(n²) versus O(n log n); memoization; redesigning an algorithm to lower its order.

| # | Exercise | File | Concepts |
|---|---|---|---|
| N13-E01 | Orders of growth | [`01_orders_of_growth.inv`](en/level13/01_orders_of_growth.inv) | big-O notation, O(log n), O(n²) |
| N13-E02 | Linear versus binary search | [`02_linear_vs_binary.inv`](en/level13/02_linear_vs_binary.inv) | worst case, O(n), O(log n) |
| N13-E03 | O(n²) versus O(n log n): bubble and merge sort | [`03_bubble_vs_merge.inv`](en/level13/03_bubble_vs_merge.inv) | O(n²), O(n log n), empirical analysis |
| N13-E04 | From exponential to linear: memoization | [`04_memoization.inv`](en/level13/04_memoization.inv) | memoization, dynamic programming, O(2^n) |
| N13-E05 | Best, worst and average case: insertion sort | [`05_best_and_worst_case.inv`](en/level13/05_best_and_worst_case.inv) | best case, worst case, average case |
| N13-E06 | Maximum subarray: O(n²) versus O(n) | [`06_maximum_subarray.inv`](en/level13/06_maximum_subarray.inv) | Kadane, O(n), O(n²) |
| N13-E07 | Pair with a given sum: O(n²) versus O(n) | [`07_two_sum.inv`](en/level13/07_two_sum.inv) | two pointers, O(n), O(n²) |
| N13-E08 | Quick sort: the worst case matters | [`08_quicksort_worst_case.inv`](en/level13/08_quicksort_worst_case.inv) | quick sort, worst case, pivot |
