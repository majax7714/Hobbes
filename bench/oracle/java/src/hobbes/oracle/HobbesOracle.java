package hobbes.oracle;

import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ExpressionTree;
import com.sun.source.tree.IdentifierTree;
import com.sun.source.tree.LambdaExpressionTree;
import com.sun.source.tree.LineMap;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.NewClassTree;
import com.sun.source.tree.ParameterizedTypeTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.Plugin;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.TaskEvent;
import com.sun.source.util.TaskListener;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;
import com.sun.tools.javac.code.Flags;
import com.sun.tools.javac.tree.JCTree;

import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.ExecutableElement;
import javax.lang.model.element.Modifier;
import javax.lang.model.element.NestingKind;
import javax.lang.model.element.TypeElement;
import javax.lang.model.type.DeclaredType;
import javax.lang.model.type.TypeKind;
import javax.lang.model.type.TypeMirror;
import javax.lang.model.util.Elements;
import javax.lang.model.util.Types;
import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * The Java resolution oracle (J.M4, ADR-096; the oracle lane's O8): a
 * javac {@link Plugin} that records, for every compilation unit the
 * build compiles, what <em>the compiler itself</em> resolved each call
 * site to — the tsc-oracle's grain, by the language's own front end.
 *
 * <p>One shard per compilation unit, written to {@code
 * $HOBBES_ORACLE_OUT/<n>.json} after ANALYZE:
 * <ul>
 * <li>{@code declarations}: every method and constructor with its key
 *     ({@code owner#name(erased param types)}), file, and the line of
 *     the name identifier (D-O4's position);</li>
 * <li>{@code classes}: every class with its binary name, direct
 *     supertypes (binary names), and whether it is an interface or
 *     abstract — the hierarchy the merge computes CHA override sets
 *     over, so a virtual site's targets are every override in the
 *     compiled program, not just the declared method;</li>
 * <li>{@code sites}: every method invocation and {@code new}, at the
 *     callee identifier's line and column, with the enclosing
 *     declaration, mode {@code static} (constructor, static, private,
 *     final, {@code super.m()}) or {@code dynamic} (a virtual or
 *     interface call — the declared method rides as the site's
 *     {@code interface}), and the resolved declaration's key.</li>
 * </ul>
 *
 * <p>Keys, not positions, cross the shard boundary: Maven compiles main
 * and test sources in separate javac runs, and a test's call into main
 * resolves against a class file that carries no name line. The Go
 * merge ({@code internal/javac}) joins keys to declarations from every
 * shard of the build; a key no shard declares is external (the JDK, a
 * dependency).
 *
 * <p>No dependencies beyond the JDK: built with {@code javac} and
 * {@code jar} inside the sandbox image ({@code build.sh}). Needs
 * {@code --add-exports jdk.compiler/com.sun.tools.javac.{tree,code}} for
 * the two internals it reads: {@code JCTree.pos} — the position of a
 * declaration's <em>name</em>, which the public API does not expose —
 * and {@code Flags.GENERATEDCONSTR}, the mark on a default constructor
 * javac wrote.
 */
public final class HobbesOracle implements Plugin {
    @Override
    public String getName() {
        return "HobbesOracle";
    }

    @Override
    public void init(JavacTask task, String... args) {
        String outDir = System.getenv("HOBBES_ORACLE_OUT");
        String repo = System.getenv("HOBBES_ORACLE_REPO");
        if (outDir == null || repo == null) {
            throw new IllegalStateException("HobbesOracle: HOBBES_ORACLE_OUT and HOBBES_ORACLE_REPO must be set");
        }
        Trees trees = Trees.instance(task);
        Types types = task.getTypes();
        Elements elements = task.getElements();
        Path repoRoot = Paths.get(repo).toAbsolutePath().normalize();
        Path out = Paths.get(outDir);
        task.addTaskListener(new TaskListener() {
            @Override
            public void finished(TaskEvent e) {
                if (e.getKind() != TaskEvent.Kind.ANALYZE || e.getCompilationUnit() == null) {
                    return;
                }
                CompilationUnitTree cu = e.getCompilationUnit();
                Shard shard = new Shard();
                Path file = Paths.get(cu.getSourceFile().toUri()).toAbsolutePath().normalize();
                shard.file = file.startsWith(repoRoot)
                        ? repoRoot.relativize(file).toString().replace('\\', '/')
                        : file.toString();
                shard.generated = shard.file.contains("/target/") || shard.file.contains("/build/")
                        || shard.file.startsWith("target/") || shard.file.startsWith("build/");
                new Scanner(trees, types, elements, cu, shard).scan(cu, null);
                try {
                    Files.createDirectories(out);
                    String name = Integer.toHexString(shard.file.hashCode()) + "-"
                            + Long.toHexString(System.nanoTime()) + ".json";
                    try (Writer w = Files.newBufferedWriter(out.resolve(name), StandardCharsets.UTF_8)) {
                        shard.write(w);
                    }
                } catch (IOException ex) {
                    throw new IllegalStateException("HobbesOracle: cannot write shard: " + ex, ex);
                }
            }
        });
    }

    /** One compilation unit's facts. */
    static final class Shard {
        String file;
        boolean generated;
        int synthetic; // calls no source line makes: javac's own super() and default constructors
        final List<String[]> declarations = new ArrayList<>(); // key, kind, line
        final List<String[]> classes = new ArrayList<>();      // binary, kind, supers...
        final List<Object[]> sites = new ArrayList<>();        // line, col, caller, mode, key, ownerKind

        void write(Writer w) throws IOException {
            Json j = new Json(w);
            j.begin();
            j.str("file", file).bool("generated", generated).str("jdk", Runtime.version().toString())
                    .num("synthetic", synthetic);
            j.key("declarations").arr();
            for (String[] d : declarations) {
                j.begin().str("key", d[0]).str("kind", d[1]).num("line", Long.parseLong(d[2])).end();
            }
            j.close();
            j.key("classes").arr();
            for (String[] c : classes) {
                j.begin().str("binary", c[0]).str("kind", c[1]).key("supers").arr();
                for (int i = 2; i < c.length; i++) {
                    j.val(c[i]);
                }
                j.close().end();
            }
            j.close();
            j.key("sites").arr();
            for (Object[] s : sites) {
                j.begin().num("line", (Long) s[0]).num("col", (Long) s[1]).str("caller", (String) s[2])
                        .str("mode", (String) s[3]).str("key", (String) s[4]).str("target_kind", (String) s[5]).end();
            }
            j.close();
            j.end();
        }
    }

    /** The walk: declarations, classes and sites of one unit. */
    static final class Scanner extends TreePathScanner<Void, Void> {
        private final Trees trees;
        private final Types types;
        private final Elements elements;
        private final CompilationUnitTree cu;
        private final SourcePositions sp;
        private final LineMap lines;
        private final Shard shard;

        Scanner(Trees trees, Types types, Elements elements, CompilationUnitTree cu, Shard shard) {
            this.trees = trees;
            this.types = types;
            this.elements = elements;
            this.cu = cu;
            this.sp = trees.getSourcePositions();
            this.lines = cu.getLineMap();
            this.shard = shard;
        }

        @Override
        public Void visitClass(ClassTree node, Void unused) {
            Element el = trees.getElement(getCurrentPath());
            if (el instanceof TypeElement te) {
                List<String> row = new ArrayList<>();
                row.add(elements.getBinaryName(te).toString());
                row.add(te.getKind() == ElementKind.INTERFACE || te.getKind() == ElementKind.ANNOTATION_TYPE
                        ? "interface"
                        : te.getModifiers().contains(Modifier.ABSTRACT) ? "abstract" : "class");
                TypeMirror sup = te.getSuperclass();
                if (sup.getKind() == TypeKind.DECLARED) {
                    row.add(binary(((DeclaredType) sup).asElement()));
                }
                for (TypeMirror i : te.getInterfaces()) {
                    if (i.getKind() == TypeKind.DECLARED) {
                        row.add(binary(((DeclaredType) i).asElement()));
                    }
                }
                shard.classes.add(row.toArray(new String[0]));
            }
            return super.visitClass(node, unused);
        }

        @Override
        public Void visitMethod(MethodTree node, Void unused) {
            Element el = trees.getElement(getCurrentPath());
            if (el instanceof ExecutableElement ee && node instanceof JCTree.JCMethodDecl tree) {
                // javac's default constructor (GENERATEDCONSTR) is kept as a
                // declaration: it sits at the class line, which is where
                // `new T()` resolves and where Hobbes draws the edge (the
                // D-O4 rule for a call of a class). Its body's super() is
                // synthetic and skipped below.
                long line = lines.getLineNumber(tree.pos);
                String kind = ee.getKind() == ElementKind.CONSTRUCTOR ? "constructor" : "method";
                Element owner = ee.getEnclosingElement();
                if (owner instanceof TypeElement te
                        && (te.getNestingKind() == NestingKind.ANONYMOUS || te.getNestingKind() == NestingKind.LOCAL)) {
                    // Below Hobbes' symbol floor by decision (a local binding
                    // with the body's extent, ADR-096): the miss class says so.
                    kind = "anonymous-member";
                }
                shard.declarations.add(new String[] {key(ee), kind, Long.toString(line)});
            }
            return super.visitMethod(node, unused);
        }

        @Override
        public Void visitMethodInvocation(MethodInvocationTree node, Void unused) {
            ExpressionTree select = node.getMethodSelect();
            TreePath selectPath = new TreePath(getCurrentPath(), select);
            Element el = trees.getElement(selectPath);
            if (el instanceof ExecutableElement ee) {
                String name = ee.getSimpleName().toString();
                long end = sp.getEndPosition(cu, select);
                long pos;
                if (select instanceof IdentifierTree) {
                    pos = sp.getStartPosition(cu, select);
                } else if (select instanceof MemberSelectTree ms) {
                    name = ms.getIdentifier().toString();
                    pos = end - name.length();
                } else {
                    pos = sp.getStartPosition(cu, select);
                }
                boolean viaSuper = select instanceof MemberSelectTree ms2
                        && ms2.getExpression() instanceof IdentifierTree id
                        && id.getName().contentEquals("super");
                if (select instanceof IdentifierTree sid && sid.getName().contentEquals("super")
                        && ee.getKind() == ElementKind.CONSTRUCTOR && isSyntheticSuper(node)) {
                    shard.synthetic++;
                    return super.visitMethodInvocation(node, unused);
                }
                String mode = isStatic(ee) || viaSuper ? "static" : "dynamic";
                site(pos, ee, mode);
            }
            return super.visitMethodInvocation(node, unused);
        }

        @Override
        public Void visitNewClass(NewClassTree node, Void unused) {
            Element el = trees.getElement(getCurrentPath());
            if (el instanceof ExecutableElement ctor) {
                Tree ident = node.getIdentifier();
                if (ident instanceof ParameterizedTypeTree p) {
                    ident = p.getType();
                }
                long pos;
                if (ident instanceof MemberSelectTree ms) {
                    pos = sp.getEndPosition(cu, ident) - ms.getIdentifier().length();
                } else {
                    pos = sp.getStartPosition(cu, ident);
                }
                ExecutableElement target = ctor;
                Element owner = ctor.getEnclosingElement();
                if (owner instanceof TypeElement te && te.getNestingKind() == NestingKind.ANONYMOUS) {
                    // `new T() {..}`: what runs is the anonymous class's
                    // synthetic constructor, which calls T's. Report T's
                    // — the declaration a reader can point at; Hobbes
                    // draws `uses` here by decision, so this is a
                    // recorded recall miss class, not a contradiction.
                    target = superConstructor(te, ctor);
                }
                if (target != null) {
                    site(pos, target, "static");
                }
            }
            return super.visitNewClass(node, unused);
        }

        @Override
        public Void visitLambdaExpression(LambdaExpressionTree node, Void unused) {
            return super.visitLambdaExpression(node, unused);
        }

        /**
         * javac inserts {@code super();} into every constructor that does
         * not start with an explicit constructor call, positioned at the
         * body's opening brace — no source line makes that call. A written
         * {@code super(..)} sits on its own line inside the body.
         */
        private boolean isSyntheticSuper(MethodInvocationTree node) {
            for (TreePath p = getCurrentPath(); p != null; p = p.getParentPath()) {
                if (p.getLeaf() instanceof MethodTree m) {
                    if (m.getBody() == null) {
                        return false;
                    }
                    long bodyPos = sp.getStartPosition(cu, m.getBody());
                    long callPos = sp.getStartPosition(cu, node);
                    return callPos <= bodyPos || ((JCTree) node).pos == ((JCTree) m.getBody()).pos;
                }
            }
            return false;
        }

        private ExecutableElement superConstructor(TypeElement anonymous, ExecutableElement anonCtor) {
            TypeMirror sup = anonymous.getSuperclass();
            TypeElement base = null;
            if (sup.getKind() == TypeKind.DECLARED) {
                base = (TypeElement) ((DeclaredType) sup).asElement();
            }
            if (base == null || base.getQualifiedName().contentEquals("java.lang.Object")) {
                if (!anonymous.getInterfaces().isEmpty()) {
                    return null; // `new Runnable() {..}`: Object's constructor, no declaration to point at
                }
                return null;
            }
            String want = erasedParams(anonCtor);
            for (Element m : base.getEnclosedElements()) {
                if (m.getKind() == ElementKind.CONSTRUCTOR && erasedParams((ExecutableElement) m).equals(want)) {
                    return (ExecutableElement) m;
                }
            }
            return null;
        }

        private void site(long pos, ExecutableElement target, String mode) {
            long line = lines.getLineNumber(pos);
            long col = lines.getColumnNumber(pos) - 1;
            shard.sites.add(new Object[] {line, col, caller(), mode, key(target),
                    target.getKind() == ElementKind.CONSTRUCTOR ? "constructor" : "method"});
        }

        private boolean isStatic(ExecutableElement ee) {
            if (ee.getKind() == ElementKind.CONSTRUCTOR) {
                return true;
            }
            var mods = ee.getModifiers();
            if (mods.contains(Modifier.STATIC) || mods.contains(Modifier.PRIVATE) || mods.contains(Modifier.FINAL)) {
                return true;
            }
            Element owner = ee.getEnclosingElement();
            if (owner instanceof TypeElement te) {
                var tmods = te.getModifiers();
                if (tmods.contains(Modifier.FINAL) || te.getKind() == ElementKind.RECORD) {
                    return true;
                }
            }
            return false;
        }

        private String caller() {
            for (TreePath p = getCurrentPath(); p != null; p = p.getParentPath()) {
                Tree leaf = p.getLeaf();
                if (leaf instanceof MethodTree) {
                    Element el = trees.getElement(p);
                    if (el instanceof ExecutableElement ee) {
                        return key(ee);
                    }
                }
                if (leaf instanceof ClassTree) {
                    Element el = trees.getElement(p);
                    if (el instanceof TypeElement te) {
                        return binary(te) + "#<clinit>";
                    }
                }
            }
            return "<unit>";
        }

        private String key(ExecutableElement ee) {
            Element owner = ee.getEnclosingElement();
            String ownerName = owner instanceof TypeElement te ? binary(te) : owner.toString();
            String name = ee.getKind() == ElementKind.CONSTRUCTOR ? "<init>" : ee.getSimpleName().toString();
            return ownerName + "#" + name + "(" + erasedParams(ee) + ")";
        }

        private String erasedParams(ExecutableElement ee) {
            StringBuilder sb = new StringBuilder();
            for (var p : ee.getParameters()) {
                if (sb.length() > 0) {
                    sb.append(',');
                }
                sb.append(typeName(types.erasure(p.asType())));
            }
            return sb.toString();
        }

        /**
         * An erased type's name without type annotations: a source-compiled
         * symbol and a class-file one print {@code @Nullable java.lang.String}
         * and {@code java.lang.String} for the same parameter (jsoup's
         * jspecify annotations, the first real cell: every test→main
         * constructor key missed its declaration). Keys must join across
         * compilations, so the name is built from the element, never from
         * {@code toString}.
         */
        private String typeName(TypeMirror t) {
            switch (t.getKind()) {
                case DECLARED:
                    return binary(((DeclaredType) t).asElement());
                case ARRAY:
                    return typeName(types.erasure(((javax.lang.model.type.ArrayType) t).getComponentType())) + "[]";
                case TYPEVAR:
                    return typeName(types.erasure(((javax.lang.model.type.TypeVariable) t).getUpperBound()));
                default:
                    return t.getKind().name().toLowerCase();
            }
        }

        private String binary(Element te) {
            return te instanceof TypeElement t ? elements.getBinaryName(t).toString() : te.toString();
        }
    }

    /** A minimal JSON writer: no dependency, no reflection. */
    static final class Json {
        private final Writer w;
        private final java.util.ArrayDeque<boolean[]> stack = new java.util.ArrayDeque<>();
        private boolean afterKey;

        Json(Writer w) {
            this.w = w;
        }

        private void sep() throws IOException {
            if (afterKey) {
                afterKey = false;
                return;
            }
            boolean[] top = stack.peek();
            if (top != null) {
                if (!top[0]) {
                    w.write(',');
                }
                top[0] = false;
            }
        }

        Json begin() throws IOException {
            sep();
            w.write('{');
            stack.push(new boolean[] {true});
            return this;
        }

        Json end() throws IOException {
            w.write('}');
            stack.pop();
            return this;
        }

        Json arr() throws IOException {
            sep();
            w.write('[');
            stack.push(new boolean[] {true});
            return this;
        }

        Json close() throws IOException {
            w.write(']');
            stack.pop();
            return this;
        }

        Json key(String k) throws IOException {
            sep();
            w.write(quote(k));
            w.write(':');
            afterKey = true;
            return this;
        }

        Json val(String v) throws IOException {
            sep();
            w.write(quote(v));
            return this;
        }

        Json str(String k, String v) throws IOException {
            return key(k).val(v);
        }

        Json num(String k, long v) throws IOException {
            key(k);
            sep();
            w.write(Long.toString(v));
            return this;
        }

        Json bool(String k, boolean v) throws IOException {
            key(k);
            sep();
            w.write(Boolean.toString(v));
            return this;
        }

        static String quote(String s) {
            StringBuilder sb = new StringBuilder("\"");
            for (char c : s.toCharArray()) {
                switch (c) {
                    case '"' -> sb.append("\\\"");
                    case '\\' -> sb.append("\\\\");
                    case '\n' -> sb.append("\\n");
                    case '\r' -> sb.append("\\r");
                    case '\t' -> sb.append("\\t");
                    default -> {
                        if (c < 0x20) {
                            sb.append(String.format("\\u%04x", (int) c));
                        } else {
                            sb.append(c);
                        }
                    }
                }
            }
            return sb.append('"').toString();
        }
    }
}
