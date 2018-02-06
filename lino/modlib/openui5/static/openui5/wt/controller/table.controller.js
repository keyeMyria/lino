sap.ui.define([
	"sap/ui/core/mvc/Controller",
	"sap/ui/model/json/JSONModel",
	"sap/ui/unified/Menu",
	"sap/ui/unified/MenuItem",
	"sap/m/MessageToast",
	"sap/ui/core/format/DateFormat"
], function(Controller, JSONModel, Menu, MenuItem, MessageToast, DateFormat) {
	"use strict";

	return Controller.extend("sap.ui.demo.wt.controller.table", {

		onInit : function () {
			var oView = this.getView();

			// set explored app's demo model on this sample
			var oJSONModel = this.initSampleDataModel();
			oView.setModel(oJSONModel);

			oView.setModel(new JSONModel({
				showVisibilityMenuEntry: false,
				showFreezeMenuEntry: false,
				enableCellFilter: false
			}), "ui");
		},

		initSampleDataModel : function() {
			var oModel = new JSONModel();

			var oDateFormat = DateFormat.getDateInstance({source: {pattern: "timestamp"}, pattern: "dd/MM/yyyy"});

			jQuery.ajax(this.getView().byId("MAIN_TABLE").data("url"), {
				dataType: "json",
				success: function (oData) {
//					var aTemp1 = [];
//					var aTemp2 = [];
//					var aSuppliersData = [];
//					var aCategoryData = [];
//					for (var i = 0; i < oData.ProductCollection.length; i++) {
//						var oProduct = oData.ProductCollection[i];
//						if (oProduct.SupplierName && jQuery.inArray(oProduct.SupplierName, aTemp1) < 0) {
//							aTemp1.push(oProduct.SupplierName);
//							aSuppliersData.push({Name: oProduct.SupplierName});
//						}
//						if (oProduct.Category && jQuery.inArray(oProduct.Category, aTemp2) < 0) {
//							aTemp2.push(oProduct.Category);
//							aCategoryData.push({Name: oProduct.Category});
//						}
//						oProduct.DeliveryDate = (new Date()).getTime() - (i % 10 * 4 * 24 * 60 * 60 * 1000);
//						oProduct.DeliveryDateStr = oDateFormat.format(new Date(oProduct.DeliveryDate));
//						oProduct.Heavy = oProduct.WeightMeasure > 1000 ? "true" : "false";
//						oProduct.Available = oProduct.Status == "Available" ? true : false;
//					}
//
//					oData.Suppliers = aSuppliersData;
//					oData.Categories = aCategoryData;

					oModel.setData(oData);
				},
				error: function () {
					jQuery.sap.log.error("failed to load json");
				}
			});

			return oModel;
		},

		onColumnSelect : function (oEvent) {
			var oCurrentColumn = oEvent.getParameter("column");
			var oImageColumn = this.getView().byId("image");
			if (oCurrentColumn === oImageColumn) {
				MessageToast.show("Column header " + oCurrentColumn.getLabel().getText() + " pressed.");
			}
		},

		onColumnMenuOpen: function (oEvent) {
			var oCurrentColumn = oEvent.getSource();
			var oImageColumn = this.getView().byId("image");
			if (oCurrentColumn != oImageColumn) {
				return;
			}

			//Just skip opening the column Menu on column "Image"
			oEvent.preventDefault();
		},

		onProductIdCellContextMenu : function (oEvent) {
			if (sap.ui.Device.support.touch) {
				return; //Do not use context menus on touch devices
			}

			if (oEvent.getParameter("columnId") != this.getView().createId("productId")) {
				return; //Custom context menu for product id column only
			}

			oEvent.preventDefault();

			var oRowContext = oEvent.getParameter("rowBindingContext");

			if (!this._oIdContextMenu) {
				this._oIdContextMenu = new Menu();
				this.getView().addDependent(this._oIdContextMenu);
			}

			this._oIdContextMenu.destroyItems();
			this._oIdContextMenu.addItem(new MenuItem({
				text: "My Custom Cell Action",
				select: function() {
					MessageToast.show("Context action triggered on Column 'Product ID' on id '" + oRowContext.getProperty("ProductId") + "'.");
				}
			}));

			//Open the menu on the cell
			var oCellDomRef = oEvent.getParameter("cellDomRef");
			var eDock = sap.ui.core.Popup.Dock;
			this._oIdContextMenu.open(false, oCellDomRef, eDock.BeginTop, eDock.BeginBottom, oCellDomRef, "none none");
		},

		onQuantityCustomItemSelect : function(oEvent) {
			MessageToast.show("Some custom action triggered on column 'Quantity'.");
		},

		onQuantitySort : function(oEvent) {
			var bAdd = oEvent.getParameter("ctrlKey") === true;
			var oColumn = this.getView().byId("quantity");
			var sOrder = oColumn.getSortOrder() == "Ascending" ? "Descending" : "Ascending";

			this.getView().byId("table").sort(oColumn, sOrder, bAdd);
		},

		showInfo : function(oEvent) {
			try {
				jQuery.sap.require("sap.ui.table.sample.TableExampleUtils");
				sap.ui.table.sample.TableExampleUtils.showInfo(jQuery.sap.getModulePath("sap.ui.table.sample.Menus", "/info.json"), oEvent.getSource());
			} catch (e) {
				// nothing
			}
		}

	});

});
