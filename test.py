# Triggers for every wired scrut rule.
# Evaluated with DEFAULT_LIMITS + DEFAULT_RULES (all rules on, default thresholds).

# 1. max_parameters (5) -> 6 args
def too_many_params(a, b, c, d, e, f):
    return a + b + c + d + e + f

# 2. return_statements (3) -> 4 returns
def many_returns(x):
    if x == 0: return 'zero'
    if x == 1: return 'one'
    if x == 2: return 'two'
    return 'many'

# 3. local_variables (15) -> 16 locals
def many_locals():
    a1 = 1
    a2 = 2
    a3 = 3
    a4 = 4
    a5 = 5
    a6 = 6
    a7 = 7
    a8 = 8
    a9 = 9
    a10 = 10
    a11 = 11
    a12 = 12
    a13 = 13
    a14 = 14
    a15 = 15
    a16 = 16
    return a1 + a16

# 4. nested_function
def outer(): 
    def inner():
        return 1
    return inner

# 5. boolean_complexity (5) -> 6 operands
def bool_chain(a, b, c, d, e, f, g):
    if a and b and c and d and e and f and g:
        return 1
    return 0

# 6. if_else_chain (5) -> 6 elif branches
def long_elif(x):
    if x==1: return '1'
    elif x==2: return '2'
    elif x==3: return '3'
    elif x==4: return '4'
    elif x==5: return '5'
    elif x==6: return '6'
    return '7'

# 7. complexity (10) -> 11 ifs => 12
def too_complex(a):
    if a: pass
    if a: pass
    if a: pass
    if a: pass
    if a: pass
    if a: pass
    if a: pass
    if a: pass
    if a: pass
    if a: pass
    if a: pass
    return a

# 8. nesting (4) -> depth 5
def deeply_nested():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        return 1
    return 0

# 9. large_lambda (5) -> lambda body 6+ nodes
def lambda_user():
    f = lambda x: x + 1 + 1 + 1 + 1 + 1 + 1
    return f(0)

# 10. large_comprehension (10) -> 11+ nodes
def big_comp():
    return [(x+y+z) for x in range(5) for y in range(5) for z in range(5)]

# 11. duplicate branch (empty_except rule detects dups)
def dup(a):
    if a == 1: return 'same'
    elif a == 2: return 'same'
    return 'x'

def dup2(a):
    if a == 3: return 'same'
    elif a == 4: return 'same'
    return 'x'

# 12. async_without_await
async def async_no_await():
    return 1

# 13. max_class_lines (200) -> 201-line class
class BigClass:
    """
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
x
    """
    pass

# 14. max_function_lines (50) -> 51 lines
def long_function(a):
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    x = a
    return x























































# 15. bare_except -> bare except handler
def bare_handler():
    try:
        return 1
    except:
        return 0
