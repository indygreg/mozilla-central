/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is the Narcissus JavaScript engine.
 *
 * The Initial Developer of the Original Code is
 * Brendan Eich <brendan@mozilla.org>.
 * Portions created by the Initial Developer are Copyright (C) 2004
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 *
 * ***** END LICENSE BLOCK ***** */

/*
 * Narcissus - JS implemented in JS.
 *
 * Execution of parse trees.
 *
 * XXX Standard classes are bootlegged from the host JS environment.  Until
 *     Array and String are metacircular,
 *       load('js.js');
 *       evaluate(snarf('js.js'));
 *     will fail due to pigeon-hole problems in standard class prototypes.
 *     First such error concerns Array.prototype.top not being callable from
 *     the host engine, because it has been overwritten with a target object
 *     (FunctionObject) that the host engine cannot call.
 */

const GLOBAL_CODE = 0, EVAL_CODE = 1, FUNCTION_CODE = 2;

function ExecutionContext(type) {
    this.type = type;
}

var global = {
    // Value properties.
    NaN: NaN, Infinity: Infinity, undefined: undefined,

    // Function properties.
    eval: function eval (s) {
        if (typeof s != "string")
            return s;

        var x = ExecutionContext.current;
        var x2 = new ExecutionContext(EVAL_CODE);
        x2.thisObject = x.thisObject;
        x2.caller = x.caller;
        x2.callee = x.callee;
        x2.scope = x.scope;
        ExecutionContext.current = x2;
        try {
            execute(compile(s), x2);
        } catch (e if e == THROW) {
            x.result = x2.result;
            throw e;
        } finally {
            ExecutionContext.current = x;
        }
        return x2.result;
    },
    parseInt: parseInt, parseFloat: parseFloat,
    isNaN: isNaN, isFinite: isFinite,
    decodeURI: decodeURI, encodeURI: encodeURI,
    decodeURIComponent: decodeURIComponent,
    encodeURIComponent: encodeURIComponent,

    // Class constructors.
    Object: Object,
    Function: function Function() {
        var p = "", b = "", n = arguments.length;
        if (n) {
            var m = n - 1;
            if (m) {
                p += arguments[0];
                for (var k = 1; k < m; k++)
                    p += "," + arguments[k];
            }
            b += arguments[m];
        }
        var f = compile("function (" + p + ") {" + b + "}");
        var s = {object: global, parent: null};
        return new FunctionObject(f, s);
    },
    Array: Array, String: String, Boolean: Boolean, Number: Number,
    Date: Date, RegExp: RegExp,
    Error: Error, EvalError: EvalError, RangeError: RangeError,
    ReferenceError: ReferenceError, SyntaxError: SyntaxError,
    TypeError: TypeError, URIError: URIError,

    // Other properties.
    Math: Math
};

var XCp = ExecutionContext.prototype;
ExecutionContext.current = XCp.caller = XCp.callee = null;
XCp.scope = {object: global, parent: null};
XCp.thisObject = global;
XCp.result = undefined;
XCp.target = null;

function Reference(base, propertyName, node) {
    this.base = base;
    this.propertyName = propertyName;
    this.node = node;
}

Reference.prototype.toString = function () { return this.node.getSource(); }

function getValue(v) {
    if (v instanceof Reference) {
        if (!v.base)
            throw new ReferenceError(v.propertyName + " is not defined");
        return v.base[v.propertyName];
    }
    return v;
}

function putValue(v, w) {
    if (v instanceof Reference)
        return (v.base || global)[v.propertyName] = w;
    throw new ReferenceError("Invalid assignment left-hand side");
}

function isPrimitive(v) {
    var t = typeof v;
    return (t == "object") ? v === null : t != "function";
}

function isObject(v) {
    var t = typeof v;
    return (t == "object") ? v !== null : t == "function";
}

// If r instanceof Reference, v == getValue(r); else v === r.
function toObject(v, r) {
    switch (typeof v) {
      case "undefined":
        throw new TypeError(r + " has no properties");
      case "boolean":
        return new Boolean(v);
      case "number":
        return new Number(v);
      case "string":
        return new String(v);
      case "object":
        if (v === null)
            throw new TypeError(r + " has no properties");
    }
    return v;
}

function execute(n, x) {
    var a, f, i, j, r, s, t, u, v;

    switch (n.type) {
      case FUNCTION:
        if (!n.declared) {
            if (n.name) {
                t = new Object;
                x.scope = {object: t, parent: x.scope};
                try {
                    v = new FunctionObject(n, x.scope);
                    t.__defineProperty__(n.name, v, true, true);
                } finally {
                    x.scope = x.scope.parent;
                }
            } else {
                v = new FunctionObject(n, x.scope);
            }
        }
        break;

      case SCRIPT:
        t = x.scope.object;
        a = n.funDecls;
        for (i = 0, j = a.length; i < j; i++) {
            s = a[i].name;
            f = new FunctionObject(a[i], x.scope);
            t.__defineProperty__(s, f, x.type != EVAL_CODE);
        }
        a = n.varDecls;
        for (i = 0, j = a.length; i < j; i++) {
            u = a[i];
            s = u.name;
            if (u.readOnly && t.hasOwnProperty(s))
                throw new TypeError("Redeclaration of const " + s);
            if (u.readOnly || !t.hasOwnProperty(s)) {
                t.__defineProperty__(s, undefined, x.type != EVAL_CODE,
                                     u.readOnly);
            }
        }
        // FALL THROUGH

      case BLOCK:
        for (i = 0, j = n.length; i < j; i++)
            execute(n[i], x);
        break;

      case IF:
        if (getValue(execute(n.condition, x)))
            execute(n.thenPart, x);
        else if (n.elsePart)
            execute(n.elsePart, x);
        break;

      case SWITCH:
        s = getValue(execute(n.discriminant, x));
        a = n.cases;
        var matchDefault = false;
      switch_loop:
        for (i = 0, j = a.length; ; i++) {
            if (i == j) {
                if (n.defaultIndex >= 0) {
                    i = n.defaultIndex - 1; // no case matched, do default
                    matchDefault = true;
                    continue;
                }
                break;                      // no default, exit switch_loop
            }
            t = a[i];                       // next case (might be default!)
            if (t.type == CASE) {
                u = getValue(execute(t.caseLabel, x));
            } else {
                if (!matchDefault)          // not defaulting, skip for now
                    continue;
                u = s;                      // force match to do default
            }
            if (u === s) {
                for (;;) {                  // this loop exits switch_loop
                    if (t.statements.length) {
                        try {
                            execute(t.statements, x);
                        } catch (e if e == BREAK && x.target == n) {
                            break switch_loop;
                        }
                    }
                    if (++i == j)
                        break switch_loop;
                    t = a[i];
                }
                // NOT REACHED
            }
        }
        break;

      case FOR:
        n.setup && getValue(execute(n.setup, x));
        // FALL THROUGH
      case WHILE:
        while (!n.condition || getValue(execute(n.condition, x))) {
            try {
                execute(n.body, x);
            } catch (e if e == BREAK && x.target == n) {
                break;
            } catch (e if e == CONTINUE && x.target == n) {
                continue;
            }
            n.update && getValue(execute(n.update, x));
        }
        break;

      case FOR_IN:
        u = n.varDecl;
        if (u)
            execute(u, x);
        r = n.iterator;
        s = execute(n.object, x);
        t = toObject(getValue(s), s);
        a = [];
        for (i in t)
            a.push(i);
        for (i = 0, j = a.length; i < j; i++) {
            putValue(execute(r, x), a[i]);
            try {
                execute(n.body, x);
            } catch (e if e == BREAK && x.target == n) {
                break;
            } catch (e if e == CONTINUE && x.target == n) {
                continue;
            }
        }
        break;

      case DO:
        do {
            try {
                execute(n.body, x);
            } catch (e if e == BREAK && x.target == n) {
                break;
            } catch (e if e == CONTINUE && x.target == n) {
                continue;
            }
        } while (getValue(execute(n.condition, x)));
        break;

      case BREAK:
      case CONTINUE:
        x.target = n.target;
        throw n.type;

      case TRY:
        try {
            execute(n.tryBlock, x);
        } catch (e if e == THROW && (j = n.catchClauses.length)) {
            e = x.result;
            x.result = undefined;
            for (i = 0; ; i++) {
                if (i == j) {
                    x.result = e;
                    throw THROW;
                }
                t = n.catchClauses[i];
                x.scope = {object: {}, parent: x.scope};
                x.scope.object.__defineProperty__(t.varName, e, true);
                try {
                    if (t.guard && !getValue(execute(t.guard, x)))
                        continue;
                    execute(t.block, x);
                    break;
                } finally {
                    x.scope = x.scope.parent;
                }
            }
        } finally {
            if (n.finallyBlock)
                execute(n.finallyBlock, x);
        }
        break;

      case THROW:
        x.result = getValue(execute(n.exception, x));
        throw THROW;

      case RETURN:
        x.result = getValue(execute(n.value, x));
        throw RETURN;

      case WITH:
        r = execute(n.object, x);
        t = toObject(getValue(r), r);
        x.scope = {object: t, parent: x.scope};
        try {
            execute(n.body, x);
        } finally {
            x.scope = x.scope.parent;
        }
        break;

      case VAR:
      case CONST:
        for (i = 0, j = n.length; i < j; i++) {
            u = n[i].initializer;
            if (!u)
                continue;
            t = n[i].name;
            for (s = x.scope; s; s = s.parent) {
                if (s.object.hasOwnProperty(t))
                    break;
            }
            u = getValue(execute(u, x));
            if (n.type == CONST)
                s.object.__defineProperty__(t, u, x.type != EVAL_CODE, true);
            else
                s.object[t] = u;
        }
        break;

      case DEBUGGER:
        throw "NYI: " + tokens[n.type];

      case SEMICOLON:
        if (n.expression)
            x.result = getValue(execute(n.expression, x));
        break;

      case LABEL:
        try {
            execute(n.statement, x);
        } catch (e if e == BREAK && x.target == n.statement) {
        }
        break;

      case COMMA:
        for (i = 0, j = n.length; i < j; i++)
            v = getValue(execute(n[i], x));
        break;

      case ASSIGN:
        r = execute(n[0], x);
        t = n[0].assignOp;
        if (t)
            u = getValue(r);
        v = getValue(execute(n[1], x));
        if (t) {
            switch (t) {
              case BITWISE_OR:  v = u | v; break;
              case BITWISE_XOR: v = u ^ v; break;
              case BITWISE_AND: v = u & v; break;
              case LSH:         v = u << v; break;
              case RSH:         v = u >> v; break;
              case URSH:        v = u >>> v; break;
              case PLUS:        v = u + v; break;
              case MINUS:       v = u - v; break;
              case MUL:         v = u * v; break;
              case DIV:         v = u / v; break;
              case MOD:         v = u % v; break;
            }
        }
        putValue(r, v);
        break;

      case CONDITIONAL:
        v = getValue(execute(n[0], x)) ? getValue(execute(n[1], x))
                                       : getValue(execute(n[2], x));
        break;

      case OR:
        v = getValue(execute(n[0], x)) || getValue(execute(n[1], x));
        break;

      case AND:
        v = getValue(execute(n[0], x)) && getValue(execute(n[1], x));
        break;

      case BITWISE_OR:
        v = getValue(execute(n[0], x)) | getValue(execute(n[1], x));
        break;

      case BITWISE_XOR:
        v = getValue(execute(n[0], x)) ^ getValue(execute(n[1], x));
        break;

      case BITWISE_AND:
        v = getValue(execute(n[0], x)) & getValue(execute(n[1], x));
        break;

      case EQ:
        v = getValue(execute(n[0], x)) == getValue(execute(n[1], x));
        break;

      case NE:
        v = getValue(execute(n[0], x)) != getValue(execute(n[1], x));
        break;

      case STRICT_EQ:
        v = getValue(execute(n[0], x)) === getValue(execute(n[1], x));
        break;

      case STRICT_NE:
        v = getValue(execute(n[0], x)) !== getValue(execute(n[1], x));
        break;

      case LT:
        v = getValue(execute(n[0], x)) < getValue(execute(n[1], x));
        break;

      case LE:
        v = getValue(execute(n[0], x)) <= getValue(execute(n[1], x));
        break;

      case GE:
        v = getValue(execute(n[0], x)) >= getValue(execute(n[1], x));
        break;

      case GT:
        v = getValue(execute(n[0], x)) > getValue(execute(n[1], x));
        break;

      case IN:
        v = getValue(execute(n[0], x)) in getValue(execute(n[1], x));
        break;

      case INSTANCEOF:
        t = getValue(execute(n[0], x));
        u = getValue(execute(n[1], x));
        if (isObject(u) && typeof u.__hasInstance__ == "function")
            v = u.__hasInstance__(t);
        else
            v = t instanceof u;
        break;

      case LSH:
        v = getValue(execute(n[0], x)) << getValue(execute(n[1], x));
        break;

      case RSH:
        v = getValue(execute(n[0], x)) >> getValue(execute(n[1], x));
        break;

      case URSH:
        v = getValue(execute(n[0], x)) >>> getValue(execute(n[1], x));
        break;

      case PLUS:
        v = getValue(execute(n[0], x)) + getValue(execute(n[1], x));
        break;

      case MINUS:
        v = getValue(execute(n[0], x)) - getValue(execute(n[1], x));
        break;

      case MUL:
        v = getValue(execute(n[0], x)) * getValue(execute(n[1], x));
        break;

      case DIV:
        v = getValue(execute(n[0], x)) / getValue(execute(n[1], x));
        break;

      case MOD:
        v = getValue(execute(n[0], x)) % getValue(execute(n[1], x));
        break;

      case DELETE:
        t = execute(n[0], x);
        v = !(t instanceof Reference) || delete t.base[t.propertyName];
        break;

      case VOID:
        getValue(execute(n[0], x));
        break;

      case TYPEOF:
        t = execute(n[0], x);
        if (t instanceof Reference)
            t = t.base ? t.base[t.propertyName] : undefined;
        v = typeof t;
        break;

      case NOT:
        v = !getValue(execute(n[0], x));
        break;

      case BITWISE_NOT:
        v = ~getValue(execute(n[0], x));
        break;

      case UNARY_PLUS:
        v = +getValue(execute(n[0], x));
        break;

      case UNARY_MINUS:
        v = -getValue(execute(n[0], x));
        break;

      case INCREMENT:
      case DECREMENT:
        t = execute(n[0], x);
        u = Number(getValue(t));
        if (n.postfix)
            v = u;
        putValue(t, (n.type == INCREMENT) ? ++u : --u);
        if (!n.postfix)
            v = u;
        break;

      case DOT:
        r = execute(n[0], x);
        t = getValue(r);
        u = n[1].value;
        v = new Reference(toObject(t, r), u, n);
        break;

      case INDEX:
        r = execute(n[0], x);
        t = getValue(r);
        u = getValue(execute(n[1], x));
        v = new Reference(toObject(t, r), String(u), n);
        break;

      case LIST:
        // Curse ECMA for specifying that arguments is not an Array object!
        v = {};
        for (i = 0, j = n.length; i < j; i++) {
            u = getValue(execute(n[i], x));
            v.__defineProperty__(i, u, false, false, true);
        }
        v.__defineProperty__('length', i, false, false, true);
        break;

      case CALL:
        r = execute(n[0], x);
        a = execute(n[1], x);
        f = getValue(r);
        if (isPrimitive(f) || typeof f.__call__ != "function")
            throw new TypeError(r + " is not callable");
        t = (r instanceof Reference) ? r.base : null;
        if (t instanceof Activation)
            t = null;
        v = f.__call__(t, a, x);
        break;

      case NEW:
      case NEW_WITH_ARGS:
        r = execute(n[0], x);
        f = getValue(r);
        a = (n.type == NEW) ? {length: 0} : execute(n[1], x);
        if (isPrimitive(f) || typeof f.__construct__ != "function")
            throw new TypeError(r + " is not a constructor");
        v = f.__construct__(a, x);
        break;

      case ARRAY_INIT:
        v = [];
        for (i = 0, j = n.length; i < j; i++) {
            if (n[i])
                v[i] = getValue(execute(n[i], x));
        }
        v.length = j;
        break;

      case OBJECT_INIT:
        v = {};
        for (i = 0, j = n.length; i < j; i++) {
            t = n[i];
            if (t.type == PROPERTY_INIT) {
                v[t[0].value] = getValue(execute(t[1], x));
            } else {
                f = new FunctionObject(t, x.scope);
                u = (t.type == GETTER) ? '__defineGetter__'
                                       : '__defineSetter__';
                v[u](t.name, thunk(f, x));
            }
        }
        break;

      case NULL:
        v = null;
        break;

      case THIS:
        v = x.thisObject;
        break;

      case TRUE:
        v = true;
        break;

      case FALSE:
        v = false;
        break;

      case IDENTIFIER:
        for (s = x.scope; s; s = s.parent) {
            if (s.object.hasOwnProperty(n.value))
                break;
        }
        v = new Reference(s && s.object, n.value, n);
        break;

      case NUMBER:
      case STRING:
      case REGEXP:
        v = n.value;
        break;

      case GROUP:
        v = execute(n[0], x);
        break;

      default:
        throw "PANIC: unknown operation " + n.type + ": " + uneval(n);
    }

    return v;
}

function Activation(f, a) {
    for (var i = 0, j = f.params.length; i < j; i++)
        this.__defineProperty__(f.params[i], a[i], true);
    this.__defineProperty__('arguments', a, true);
}

function FunctionObject(node, scope) {
    this.node = node;
    this.scope = scope;
    this.__defineProperty__('length', node.params.length, true, true, true);
    this.__defineProperty__('prototype', {constructor: this}, true);
}

var FOp = FunctionObject.prototype = {
    // Internal methods.
    __call__: function (t, a, x) {
        var x2 = new ExecutionContext(FUNCTION_CODE);
        x2.thisObject = t || global;
        x2.caller = x;
        x2.callee = this;
        a.__defineProperty__('callee', this, false, false, true);
        var f = this.node;
        x2.scope = {object: new Activation(f, a), parent: this.scope};

        ExecutionContext.current = x2;
        try {
            execute(f.body, x2);
        } catch (e if e == RETURN) {
            return x2.result;
        } catch (e if e == THROW) {
            x.result = x2.result;
            throw THROW;
        } finally {
            ExecutionContext.current = x;
        }
        return undefined;
    },

    __construct__: function (a, x) {
        var o = new Object;
        var p = this.prototype;
        if (isObject(p))
            o.__proto__ = p;
        // else o.__proto__ defaulted to Object.prototype

        var v = this.__call__(o, a, x);
        if (isObject(v))
            return v;
        return o;
    },

    __hasInstance__: function (v) {
        if (isPrimitive(v))
            return false;
        var p = this.prototype;
        if (isPrimitive(p))
            throw new TypeError("'prototype' property is not an object");
        var o;
        while ((o = v.__proto__)) {
            if (o == p)
                return true;
        }
        return false;
    },

    // Standard methods.
    toString: function () {
        return this.node.getSource();
    },

    apply: function (t, a) {
        // Curse ECMA again!
        if (typeof this.__call__ != "function") {
            throw new TypeError("Function.prototype.apply called on" +
                                " uncallable object");
        }

        if (t === undefined || t === null)
            t = global;
        else if (typeof t != "object")
            t = toObject(t, t);

        if (a === undefined || a === null) {
            a = {};
            a.__defineProperty__('length', 0, false, false, true);
        } else if (a instanceof Array) {
            var v = {};
            for (var i = 0, j = a.length; i < j; i++)
                v.__defineProperty__(i, a[i], false, false, true);
            v.__defineProperty__('length', i, false, false, true);
            a = v;
        } else if (!(a instanceof Object)) {
            // XXX check for a non-arguments object
            throw new TypeError("Second argument to Function.prototype.apply" +
                                " must be an array or arguments object");
        }

        return this.__call__(t, a, ExecutionContext.current);
    },

    call: function (t) {
        // Curse ECMA a third time!
        var a = Array.prototype.splice.call(arguments, 1);
        return this.apply(t, a);
    }
};

// Connect Function.prototype and Function.prototype.constructor.
global.Function.__defineProperty__('prototype', FOp, true, true, true);
FOp.__defineProperty__('constructor', global.Function, false, false, true);

// Help native and host-scripted functions be like FunctionObjects.
var Fp = Function.prototype;

Fp.__call__ = function (t, a, x) {
    // Curse ECMA yet again!
    a = Array.prototype.splice.call(a, 0, a.length);
    return this.apply(t, a);
};

Fp.__construct__ = function (a, x) {
    switch (a.length) {
      case 0:
        return new this();
      case 1:
        return new this(a[0]);
      case 2:
        return new this(a[0], a[1]);
      case 3:
        return new this(a[0], a[1], a[2]);
      case 4:
        return new this(a[0], a[1], a[2], a[3]);
      case 5:
        return new this(a[0], a[1], a[2], a[3], a[4]);
      case 6:
        return new this(a[0], a[1], a[2], a[3], a[4], a[5]);
      case 7:
        return new this(a[0], a[1], a[2], a[3], a[4], a[5], a[6]);
    }
    throw "PANIC: too many arguments to constructor";
};

Fp.__hasInstance__ = function (v) {
    // Since we use native functions such as Date along with host ones such
    // as global.eval, we want both to be considered instances of the native
    // Function constructor.
    return v instanceof Function || v instanceof global.Function;
};

function thunk(f, x) {
    return function () { return f.__call__(this, arguments, x); };
}

function evaluate(s) {
    var x = ExecutionContext.current;
    var x2 = new ExecutionContext(GLOBAL_CODE);
    ExecutionContext.current = x2;
    try {
        execute(compile(s), x2);
    } finally {
        ExecutionContext.current = x;
    }
    return x2.result;
}
