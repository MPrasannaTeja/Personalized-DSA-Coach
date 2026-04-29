"""
All LLM prompt templates for the DSA Coach agent.

Keeping prompts in one place makes them easy to version and A/B test.
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ── Phase / Topic catalogue (mirrors frontend) ────────────────────────────────
PHASES = [
    {
        "id": 1, "title": "Phase 1 — Foundation Reset",
        "topics": [
            {"id": "arrays",     "name": "Arrays & Strings",    "min_problems": 15, "patterns": ["Two Pointers", "Sliding Window", "Prefix Sum", "Kadane's Algorithm", "Monotonic Stack"]},
            {"id": "binsearch",  "name": "Binary Search",       "min_problems": 12, "patterns": ["Binary Search on index", "Binary Search on answer", "Rotated array search"]},
            {"id": "linkedlist", "name": "Linked Lists",        "min_problems": 10, "patterns": ["Fast & Slow Pointers", "Reverse In-Place", "Dummy Head Node", "Floyd's Cycle", "Merge Two Lists"]},
        ],
    },
    {
        "id": 2, "title": "Phase 2 — The Big Unlock",
        "topics": [
            {"id": "recursion", "name": "Recursion & Backtracking", "min_problems": 12, "patterns": ["Recursion tree", "Subsets/Permutations", "N-Queens", "Pruning"]},
            {"id": "trees",     "name": "Trees & BST",             "min_problems": 25, "patterns": ["DFS Preorder", "DFS Inorder (BST)", "DFS Postorder", "BFS Level Order", "LCA", "Tree Diameter"]},
            {"id": "heaps",     "name": "Heaps & Priority Queue",  "min_problems": 12, "patterns": ["Min/Max Heap", "Top-K", "Median from stream", "K-way merge"]},
        ],
    },
    {
        "id": 3, "title": "Phase 3 — Graph World",
        "topics": [
            {"id": "graphs",    "name": "Graph Fundamentals", "min_problems": 18, "patterns": ["BFS Level Order", "DFS Preorder", "Island / Flood Fill", "Topological Sort", "Union-Find", "LCA"]},
            {"id": "advgraphs", "name": "Advanced Graphs",    "min_problems": 12, "patterns": ["Dijkstra's", "Bellman-Ford", "Floyd-Warshall", "Prim's/Kruskal's MST", "Union-Find"]},
        ],
    },
    {
        "id": 4, "title": "Phase 4 — DP Demystified",
        "topics": [
            {"id": "dp1", "name": "DP Foundation",         "min_problems": 12, "patterns": ["1D DP Array", "2D Grid DP"]},
            {"id": "dp2", "name": "Knapsack Family",       "min_problems": 12, "patterns": ["0/1 Knapsack", "Unbounded Knapsack"]},
            {"id": "dp3", "name": "Sequences & Intervals", "min_problems": 14, "patterns": ["LCS Pattern", "LIS Pattern"]},
        ],
    },
    {
        "id": 5, "title": "Phase 5 — Interview Mode",
        "topics": [
            {"id": "trie",    "name": "Trie",                    "min_problems": 8,  "patterns": ["Trie insert/search", "Prefix matching"]},
            {"id": "segtree", "name": "Segment Tree",             "min_problems": 8,  "patterns": ["Segment Tree range query", "Point update"]},
            {"id": "random",  "name": "Random Mixed Practice",    "min_problems": 30, "patterns": ["All patterns"]},
        ],
    },
]


def get_topic_by_id(topic_id: str) -> dict | None:
    for phase in PHASES:
        for topic in phase["topics"]:
            if topic["id"] == topic_id:
                return {**topic, "phase_title": phase["title"]}
    return None


# ── Coach system prompt ───────────────────────────────────────────────────────
COACH_SYSTEM = """\
You are a DSA (Data Structures & Algorithms) coach helping a student prepare for software engineering interviews.

Student context (current progress):
{context_block}

Past notes this student has written (use these to personalize hints):
{rag_context}

Your rules:
- When recommending a problem, give the exact LeetCode problem name and number
- When teaching a pattern, show a code template first, then explain why it works
- When giving a hint, give only the pattern name and ONE clue — not the full solution
- When the student shares a solution, point out what is good and what can improve
- Keep responses focused and practical
- Use markdown formatting
- If asked for explanation, use simple analogies and step-by-step breakdowns
- Always push the student to think before giving answers
"""

COACH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", COACH_SYSTEM),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{user_message}"),
])


# ── Daily assignment prompt ───────────────────────────────────────────────────
DAILY_ASSIGNMENT_SYSTEM = """\
You are a DSA coach generating a daily study assignment for a student preparing for software engineering interviews.

Student data:
{student_context}

Generate a JSON response with exactly these fields and nothing else:
{{
  "motivational_message": "2-3 sentences motivating the student based on their streak and progress",
  "problem_assignment": "Recommend {count} specific LeetCode problems with exact names and numbers. Explain why these problems fit today's topic and what pattern to focus on.",
  "recommended_difficulty": "easy or medium or hard",
  "recommended_count": {count}
}}

Return only valid JSON. No extra text before or after.
"""


NOTES_VALIDATION_SYSTEM = """\
You are a DSA coach validating a student's pattern notes after they viewed a solution.

A valid note must contain all of these:
1. The specific pattern name (example: sliding window, two pointers, BFS)
2. Why this pattern applies to this specific problem
3. The key insight or trick
4. How to recognize this pattern in future problems

Student notes to validate:
{notes}

Problem context: {problem_context}

Respond with only this JSON and nothing else:
{{
  "is_valid": true or false,
  "score": a number from 1 to 10,
  "feedback": "specific feedback about what is good or missing",
  "approved": true or false
}}

Set approved to true only if score is 6 or higher AND is_valid is true.
"""

DAILY_ASSIGNMENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", DAILY_ASSIGNMENT_SYSTEM),
    ("human", "Generate today's assignment for this student."),
])

NOTES_VALIDATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", NOTES_VALIDATION_SYSTEM),
    ("human", "Validate these notes now."),
])
