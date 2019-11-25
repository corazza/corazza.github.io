---
layout: post
title: Manipulating Java class loading mechanisms
categories: [java, security]
---


At the moment I am working as an intern in [CROZ](http://www.croz.net/), and I was tasked with creating an evaluator for Java for an online competition. It's essentially supposed to execute code sent by the competitors using JUnit (and a security framework, of course), and return some results - the final implementation is supposed to be a web application which would allow users to submit JAR files with their classes to the server and display a ranking and/or their individual points and test results.

The first problem that had to be solved was dynamically loading and unloading classes in the Java runtime, and that is what this post is about. However, this introduced a number of other problems as well - mostly due to the nature of the Java class loading system and the requirements of the application itself.

This is an example of a very simple class being tested:

```java
package evaluator.tested;

public class K {
  public boolean returnsTrue() {
    return false;
  }
}
```

And this is the JUnit test:

```java
package evaluator.tests;

import static org.junit.Assert.*;
import org.junit.*;
import evaluator.tested.*;

public class KTest {
  private K tested;

  @Before
  public void setup() {
    tested = new K();
  }

  @Test
  public void returnsTrueTest() {
    assertTrue(tested.returnsTrue());
  }
}
```

The default implementation of K always fails this test, obviously. However, the evaluator is supposed to provide alternative implementations of K (each of them found in separate JAR files), and test them as well.

This is not something done regularly in Java, and was problematic, because I wasn't used to this way of thinking: *that there can be multiple classes all sharing the same fully qualified name, coexisting in parallel or even one after another, in the same runtime.* However, these kinds of situations are possible because classes are not only identified by their fully qualified names, but also the classloaders that loaded them.

I thought initially that this would be a solution to my problem. **For each submission, I could just create a new classloader, load the class, and then have it tested.** But it's not that simple at all!

First of all, class loaders in Java exist in a hierarchy - each classloader has a single parent class loader, all the way up to the bootstrap one, which doesn't have a parent and is implemented natively. It's difficult (yet not impossible) to create an isolated classloader that would work by itself and just load the classes it was told to load. Which means that the class loaders created programmatically in order to load some class can end up not being the ones who loaded it! This is due to the hierarchy and the implementation of the `ClassLoader#loadClass()` method. **The default behavior is to simply delegate the loading to the parent classloader** - and proceed to actually load it only if every node in the chain up to the root one had not succeeded. Modifying this behavior is discouraged - and custom implementations are supposed to override the `ClassLoader#findClass()` method that is actually supposed to load and define a class as loaded by this class loader (which, by default, just throws a `ClassNotFoundException`) instead (since this fits most uses people would even have for custom class loaders).

This can be demonstrated in the following snippet of code:

```java
package com.jancorazza.snippets;
import java.lang.reflect.Method;
import java.net.URL;
import java.net.URLClassLoader;

//Class that will be loaded both automatically and programmatically
class K {
  // How many objects of this class have been instantiated
  static private int numObjects;

  // Called when the class is completely loaded
  static {
    System.out.println("Initializing");
  }

  // For each object
  {
    System.out.println("New instance");
    ++numObjects;
  }

  static public int getNumObjects() {
    return numObjects;
  }
}

public class ClassLoadingDelegationExample {
  public static void main(String[] args) {
    // Force class K to be loaded automatically
    new K();

    // Create a new classloader that can be used to dynamically load classes
    try {
      URL[] urls = {};
      URLClassLoader cl1 = new URLClassLoader(urls);

      // Attempt to load class K again
      Class<?> loadedK = cl1.loadClass("com.jancorazza.snippets.K");

      // Create a new object from the loaded class
      loadedK.newInstance();

      // Print how many instances of the the programmatically loaded class have been instantiated
      Method getNumObjects = loadedK.getMethod("getNumObjects", (Class<?> []) null);
      System.out.println("Number of objects of this type: " + getNumObjects.invoke(null, (Object[]) null));

      cl1.close();
    } catch (Exception e) {
      System.out.println(e);
      throw new RuntimeException();
    }
  }
}
```

This is the output when the code is ran:

```
Initializing
New instance
New instance
Number of objects of this type: 2
```

What's going on?

It is evident that the static initializer gets called only once. From there, it can be concluded, that the class K was loaded once - when it was first needed in the 32nd line (exactly when a class is loaded depends on the JVM implementation). In the 40th line, where `URLClassLoader` is requested to load the class once more, and then in the 42nd line where an instance of that loaded class is requested, the static initializer is not called again - because `URLClassLoader` had only returned the already loaded `com.jancorazza.snippets.K` class from its parent. Furthermore, it's obvious that the implicitly loaded class and the programmatically loaded one are the same because `com.jancorazza.snippets.K#getNumObjects()` returned 2, and not one.

Why was this a problem? Well, if the classes that I tried to load all had the same fully qualified names, and were not in fact loaded by my class loader, but rather delegated further up, **they would end up being discarded as already loaded by the `ClassLoader#findLoadedClass()` method** (at the beginning of `loadClass()`, [source line 312](http://grepcode.com/file/repository.grepcode.com/java/root/jdk/openjdk/6-b14/java/lang/ClassLoader.java#ClassLoader.loadClass%28java.lang.String%2Cboolean%29)).

To solve this, I had to somehow selectively filter all the requests for the classes that I wanted to load programmatically, and delegate all other requests which couldn't be found in URL sources.

The second issue was the fact that was impossible to change the classloader of some class at runtime (and it wouldn't do me any good either). The classloader which loaded (more specifically, called `ClassLoader#defineClass()` on the bytecode) the class was set as its current classloader - and all the references in this class will be loaded by it.

These two facts implied that in order to get the JUnit test to load the specific classes sent by the users, it was necessary for the test itself to be loaded and defined by my custom classloader.

I had to create a custom classloader that would extend `URLClassLoader`, which is able to load classes found in JAR files (in the above example the URL sources were empty so it behaved just like a regular classloader). Then, the URLs pointing to the JAR file of the user's class(es), and to the root package of the project would be set for it. Lastly, the `loadClass()` method had to be overridden with custom logic: load first, delegate later. This meant that the custom classloader would first try to find the requested class in its own URL resources, and only when it failed to find one would it delegate the search to its parent.

The result is this simple piece of code to execute a test on a custom class from a JAR file:

```java
Result resultOne = eval.performTest("/home/yann/evaltests/uploads/one.jar", "evaluator.tests.KTest");
```

This is the source code of my `ReverseURLClassLoader` which I've written:

```java
package evaluator.main;

import java.net.URL;
import java.net.URLClassLoader;

/**
 * First tries to load a class by itself, and only then delegates to parent.
 */
public class ReverseURLClassLoader extends URLClassLoader {
  public ReverseURLClassLoader(URL[] urls) {
    super(urls);
  }

  @Override
  protected synchronized Class > loadClass(String name, boolean resolve) throws ClassNotFoundException {
    Class<?> c = findLoadedClass(name);

    if (c == null) {
      try {
        c = findClass(name);
      } catch (ClassNotFoundException e) {
        c = super.loadClass(name, resolve);
        return c;
      }
    }

    if (resolve) {
      resolveClass(c);
    }

    return c;
  }
}
```

The algorithm is simple:

1. Check if class already loaded by this classloader, if so, return it (ln. 20)
2. If not, try to find the class in URL sources (JAR of the user) and return it (ln. 24)
3. If failed, call `URLClassLoader#loadClass()` which delegates to parent classloader (ln. 26)

I'm still working on the project, as I'm yet to implement the most important logic, the web application, and security.
