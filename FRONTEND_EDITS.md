# Small edits to your existing HTML pages

Your HTML, CSS, Bootstrap and JavaScript stay as they are. Django serves your files from `frontend/`, and your
current links (`index.html`, `about.html`, `classes.html` ...) and asset paths (`css/style.css` ...) keep working
because the backend answers on exactly those URLs.

Only four pages need edits, and only to swap hard-coded text for database content or to make the form submit.
Reuse **your own tags and CSS classes** in the snippets below - they only show the Django template code to insert.

> Django reads these files as templates, so if any of your inline JavaScript contains `{{` or `{%`,
> wrap that script in `{% verbatim %} ... {% endverbatim %}`.

---

## 1. `classes.html` - replace the four hard-coded class lines with

```html
{% for c in classes %}
  <li>{{ c.icon }} {{ c.name }} – {{ c.schedule_display }}</li>
{% empty %}
  <li>Class timetable coming soon.</li>
{% endfor %}
```

Renders exactly like your current text (`Yoga – Mon, Wed, Fri, 6AM - 7AM`). Optionally add a booking link:

```html
<a href="{% url 'book_class' %}">Book a class</a>
```

## 2. `membership.html` - replace the three hard-coded plans with

```html
{% for plan in plans %}
  <li><strong>{{ plan.name }}:</strong> ₹{{ plan.price|floatformat:"0" }}/month — {{ plan.description }}
      <a href="{% url 'join_plan' plan.slug %}">Join Now</a></li>
{% endfor %}
```

(Prefer to keep your single "Join Now" button under the list? Point it at `{% url 'register' %}` instead.)

## 3. `contact.html` - make the form submit to the database

Keep your own markup and classes; what matters is the `<form>` line, the `csrf_token`, and the **`name=` attributes**:

```html
{% for message in messages %}
  <p class="alert alert-{{ message.tags }}">{{ message }}</p>
{% endfor %}

<form method="post" action="{% url 'contact' %}">
  {% csrf_token %}
  <input type="text"  name="name"    placeholder="Your name"  value="{{ form.name.value|default:'' }}" required>
  {{ form.name.errors }}
  <input type="email" name="email"   placeholder="Your email" value="{{ form.email.value|default:'' }}" required>
  {{ form.email.errors }}
  <input type="tel"   name="phone"   placeholder="Phone (optional)" value="{{ form.phone.value|default:'' }}">
  {{ form.phone.errors }}
  <input type="text"  name="subject" placeholder="Subject (optional)" value="{{ form.subject.value|default:'' }}">

  <select name="plan">
    <option value="">Interested in a plan? (optional)</option>
    {% for p in plans %}
      <option value="{{ p.pk }}" {% if form.plan.value|stringformat:"s" == p.pk|stringformat:"s" %}selected{% endif %}>{{ p.name }}</option>
    {% endfor %}
  </select>

  <textarea name="message" placeholder="Your message" required>{{ form.message.value|default:'' }}</textarea>
  {{ form.message.errors }}

  {# spam trap - keep it hidden #}
  <input type="text" name="website" style="display:none" tabindex="-1" autocomplete="off">

  <button type="submit">Send Message</button>
</form>
```

## 4. Navigation on all six pages (Login / Register / My Account)

Inside your existing menu list, add:

```html
<li><a href="trainers.html">Trainers</a></li>
{% include "partials/auth_links.html" %}
```

(If your menu uses plain `<a>` tags instead of `<li>`, copy the markup from `templates/partials/auth_links.html`
and adapt the tags. Logout is a small POST form because Django 5 no longer allows logging out with a plain link.)

Also add this line just under your nav on any page where you want success/error messages to show (at least `contact.html`
if you didn't use the message loop from step 3):

```html
{% include "partials/messages.html" %}
```

## 5. Home page "Join Now" button

```html
<a href="{% url 'register' %}">Join Now</a>
```

## 6. One-time: make the *new* pages look like your site

Open `templates/base.html` and follow the three "ONE-TIME STEP" notes: paste your `<head>` links, your nav and your
footer there. The register, login, dashboard, booking, join-plan and trainers pages all inherit from it.
