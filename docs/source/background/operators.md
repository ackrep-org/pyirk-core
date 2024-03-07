(sec_operators)=
# Operators

Example from `math.py` (OCSE):


```python
I4895 = p.create_item(
    R1__has_label="mathematical operator",
    R2__has_description="general (unspecified) mathematical operator",
    R3__is_subclass_of=p.I12["mathematical object"],
)

I4895["mathematical operator"].add_method(p.create_evaluated_mapping, "_custom_call")


I5177 = p.create_item(
    R1__has_label="matmul",
    R2__has_description=("matrix multiplication operator"),
    R4__is_instance_of=I4895["mathematical operator"],
    R8__has_domain_of_argument_1=I9904["matrix"],
    R9__has_domain_of_argument_2=I9904["matrix"],
    R11__has_range_of_result=I9904["matrix"],
)

# representing the product of two matrices:

A = p.instance_of(I9904["matrix"])
B = p.instance_of(I9904["matrix"]])

# this call creates and returns a new item
# (instance of `I32["evaluated mapping"]`)
C = I5177["matmul"](A, B)

# equivalent but more readable:
mul = I5177["matmul"]
C = mul(A, B)
```
