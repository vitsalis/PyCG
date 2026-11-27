use std::cmp::Ordering;

use num_bigint::BigInt;
use ruff_python_ast::CmpOp;

use crate::builder::flow::Literal;

const F64_MANTISSA_BITS: u32 = 52;
const F64_EXPONENT_BIAS: i64 = 1075;

enum Number {
    Int(BigInt),
    Float(f64),
}

fn number(value: &Literal) -> Option<Number> {
    match value {
        Literal::Int(value) => Some(Number::Int(value.clone())),
        Literal::Bool(value) => Some(Number::Int(BigInt::from(u8::from(*value)))),
        Literal::Float(value) => Some(Number::Float(*value)),
        Literal::Str(_) | Literal::Bytes(_) | Literal::None => None,
    }
}

fn exact_integer(value: f64) -> BigInt {
    assert!(value.is_finite() && value.fract() == 0.0);
    let bits = value.to_bits();
    let exponent = i64::try_from((bits >> F64_MANTISSA_BITS) & 0x7ff).expect("eleven bits fit i64");
    let fraction = bits & ((1 << F64_MANTISSA_BITS) - 1);
    let mantissa = if exponent == 0 {
        fraction
    } else {
        fraction | (1 << F64_MANTISSA_BITS)
    };
    let shift = exponent.max(1) - F64_EXPONENT_BIAS;
    let magnitude = BigInt::from(mantissa);
    let magnitude = if shift >= 0 {
        magnitude << usize::try_from(shift).expect("a positive shift fits usize")
    } else {
        magnitude >> usize::try_from(-shift).expect("a negative shift fits usize")
    };
    if value.is_sign_negative() {
        -magnitude
    } else {
        magnitude
    }
}

fn compare_int_float(integer: &BigInt, float: f64) -> Option<Ordering> {
    if float.is_nan() {
        return None;
    }
    if float.is_infinite() {
        return Some(if float > 0.0 {
            Ordering::Less
        } else {
            Ordering::Greater
        });
    }
    let floor = exact_integer(float.floor());
    match integer.cmp(&floor) {
        Ordering::Greater if float.fract() != 0.0 => Some(Ordering::Greater),
        Ordering::Equal if float.fract() != 0.0 => Some(Ordering::Less),
        ordering => Some(ordering),
    }
}

fn compare_numbers(a: &Number, b: &Number) -> Option<Ordering> {
    match (a, b) {
        (Number::Int(a), Number::Int(b)) => Some(a.cmp(b)),
        (Number::Float(a), Number::Float(b)) => a.partial_cmp(b),
        (Number::Int(a), Number::Float(b)) => compare_int_float(a, *b),
        (Number::Float(a), Number::Int(b)) => compare_int_float(b, *a).map(Ordering::reverse),
    }
}

pub(crate) fn equal(a: &Literal, b: &Literal) -> bool {
    if let (Some(a), Some(b)) = (number(a), number(b)) {
        return compare_numbers(&a, &b) == Some(Ordering::Equal);
    }
    match (a, b) {
        (Literal::Str(a), Literal::Str(b)) => a == b,
        (Literal::Bytes(a), Literal::Bytes(b)) => a == b,
        (Literal::None, Literal::None) => true,
        _ => false,
    }
}

fn order(a: &Literal, b: &Literal) -> Result<Option<Ordering>, ()> {
    if let (Some(a), Some(b)) = (number(a), number(b)) {
        return Ok(compare_numbers(&a, &b));
    }
    match (a, b) {
        (Literal::Str(a), Literal::Str(b)) => Ok(Some(a.cmp(b))),
        (Literal::Bytes(a), Literal::Bytes(b)) => Ok(Some(a.cmp(b))),
        _ => Err(()),
    }
}

fn identical(a: &Literal, b: &Literal) -> bool {
    match (a, b) {
        (Literal::None, Literal::None) => true,
        (Literal::Bool(a), Literal::Bool(b)) => a == b,
        _ => false,
    }
}

pub(crate) fn compare(operator: CmpOp, a: &Literal, b: &Literal) -> Option<bool> {
    let holds = |accepts: fn(Ordering) -> bool| -> Option<bool> {
        order(a, b)
            .ok()
            .map(|ordering| ordering.is_some_and(accepts))
    };
    match operator {
        CmpOp::Eq => Some(equal(a, b)),
        CmpOp::NotEq => Some(!equal(a, b)),
        CmpOp::Lt => holds(Ordering::is_lt),
        CmpOp::LtE => holds(Ordering::is_le),
        CmpOp::Gt => holds(Ordering::is_gt),
        CmpOp::GtE => holds(Ordering::is_ge),
        CmpOp::Is => Some(identical(a, b)),
        CmpOp::IsNot => Some(!identical(a, b)),
        CmpOp::In | CmpOp::NotIn => unreachable!("membership is decided on the members"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn int(value: i64) -> Literal {
        Literal::Int(BigInt::from(value))
    }

    #[test]
    fn integers_and_floats_compare_exactly() {
        assert!(equal(&int(1), &Literal::Float(1.0)));
        assert!(equal(&Literal::Bool(true), &int(1)));
        assert!(!equal(&Literal::Float(f64::NAN), &Literal::Float(f64::NAN)));
        let big = Literal::Int(BigInt::from(1u64 << 53) + 1);
        assert!(!equal(&big, &Literal::Float(9_007_199_254_740_992.0)));
        assert_eq!(
            compare(CmpOp::Gt, &big, &Literal::Float(9_007_199_254_740_992.0)),
            Some(true)
        );
        assert_eq!(
            compare(CmpOp::Lt, &int(2), &Literal::Float(2.5)),
            Some(true)
        );
        assert_eq!(
            compare(CmpOp::Lt, &int(-3), &Literal::Float(-2.5)),
            Some(true)
        );
        assert_eq!(
            compare(CmpOp::Gt, &int(3), &Literal::Float(f64::INFINITY)),
            Some(false)
        );
        assert_eq!(
            compare(CmpOp::Lt, &int(3), &Literal::Float(f64::NAN)),
            Some(false)
        );
    }

    #[test]
    fn values_of_unordered_kinds_raise() {
        let text = Literal::Str(vec![97].into());
        assert_eq!(compare(CmpOp::Lt, &text, &int(1)), None);
        assert_eq!(compare(CmpOp::Lt, &Literal::None, &Literal::None), None);
        assert_eq!(compare(CmpOp::Eq, &text, &int(1)), Some(false));
        assert_eq!(
            compare(CmpOp::Is, &Literal::None, &Literal::None),
            Some(true)
        );
        assert_eq!(
            compare(CmpOp::IsNot, &Literal::Bool(true), &Literal::None),
            Some(true)
        );
    }

    #[test]
    fn floats_convert_to_their_exact_integer() {
        assert_eq!(exact_integer(0.0), BigInt::from(0));
        assert_eq!(exact_integer(-12.0), BigInt::from(-12));
        assert_eq!(
            exact_integer(1e20),
            "100000000000000000000".parse::<BigInt>().unwrap()
        );
        assert_eq!(exact_integer(2f64.powi(60)), BigInt::from(1u64 << 60));
    }
}
