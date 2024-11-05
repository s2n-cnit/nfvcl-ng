from nfvcl.models.blueprint_ng.free5gc.free5gcCore import Free5gcSubScriber

subscriber_config: Free5gcSubScriber = Free5gcSubScriber.model_validate({
   "userNumber":1,
   "plmnID":"20893",
   "ueId":"imsi-208930000000005",
   "AuthenticationSubscription":{
      "authenticationMethod":"5G_AKA",
      "sequenceNumber":"000000000023",
      "authenticationManagementField":"8000",
      "permanentKey":{
         "permanentKeyValue":"8baf473f2f8fd09487cccbd7097c6862",
         "encryptionKey":0,
         "encryptionAlgorithm":0
      },
      "milenage":{
         "op":{
            "opValue":"",
            "encryptionKey":0,
            "encryptionAlgorithm":0
         }
      },
      "opc":{
         "opcValue":"8e27b6af0e692e750f32667a3b14605d",
         "encryptionKey":0,
         "encryptionAlgorithm":0
      }
   },
   "AccessAndMobilitySubscriptionData":{
      "gpsis":[
         "msisdn-"
      ],
      "subscribedUeAmbr":{
         "uplink":"1 Gbps",
         "downlink":"2 Gbps"
      },
      "nssai":{
         "defaultSingleNssais":[],
         "singleNssais":[]
      }
   },
   "SessionManagementSubscriptionData":[],
   "SmfSelectionSubscriptionData":{
      "subscribedSnssaiInfos":{}
   },
   "AmPolicyData":{
      "subscCats":[
         "free5gc"
      ]
   },
   "SmPolicyData":{
      "smPolicySnssaiData":{}
   },
   "FlowRules":[],
   "QosFlows":[],
   "ChargingDatas":[

   ]
})
