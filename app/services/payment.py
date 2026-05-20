import stripe


def create_checkout_session(app, plan_price_id, success_url, cancel_url):
    stripe.api_key = app.config["STRIPE_SECRET_KEY"]
    if not stripe.api_key:
        raise ValueError("Stripe key missing")

    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": plan_price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        billing_address_collection="required",
        allow_promotion_codes=True,
    )
