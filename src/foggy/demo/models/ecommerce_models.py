"""E-commerce demo models aligned with Java FactSalesModel.tm / FactOrderModel.tm etc.

Maps to the foggy_test MySQL database (Docker localhost:13306).
Star schema: fact tables JOIN to dimension tables via surrogate keys.

Tables:
  Fact:  fact_sales, fact_order, fact_payment, fact_return, fact_inventory_snapshot
  Dim:   dim_date, dim_product, dim_customer, dim_store, dim_channel, dim_promotion
"""

from typing import Dict

from foggy.dataset_model.definitions.base import AggregationType, DimensionType
from foggy.dataset_model.impl.model import (
    DbTableModelImpl,
    DbModelDimensionImpl,
    DbModelMeasureImpl,
    DimensionJoinDef,
    DimensionPropertyDef,
)


# ==================== Shared Dimension JoinDefs ====================

def _dim_date(name: str = "salesDate", caption: str = "销售日期",
              description: str = "订单发生的日期") -> DimensionJoinDef:
    return DimensionJoinDef(
        name=name,
        table_name="dim_date",
        foreign_key="date_key",
        primary_key="date_key",
        caption_column="full_date",
        caption=caption,
        description=description,
        alias="dd",
        properties=[
            DimensionPropertyDef(column="year", caption="年", description="年份"),
            DimensionPropertyDef(column="quarter", caption="季度", description="季度（1-4）"),
            DimensionPropertyDef(column="month", caption="月", description="月份（1-12）"),
            DimensionPropertyDef(column="week_of_year", name="week", caption="周", description="ISO周号（1-53）"),
            DimensionPropertyDef(column="month_name", name="monthName", caption="月份名称"),
            DimensionPropertyDef(column="day_of_week", name="dayOfWeek", caption="周几"),
            DimensionPropertyDef(column="is_weekend", name="isWeekend", caption="是否周末"),
        ],
    )


def _dim_product(caption: str = "商品") -> DimensionJoinDef:
    return DimensionJoinDef(
        name="product",
        table_name="dim_product",
        foreign_key="product_key",
        primary_key="product_key",
        caption_column="product_name",
        caption=caption,
        alias="dp",
        properties=[
            DimensionPropertyDef(column="product_id", name="productId", caption="商品ID"),
            DimensionPropertyDef(column="category_id", name="categoryId", caption="一级品类ID"),
            DimensionPropertyDef(column="category_name", name="categoryName", caption="一级品类名称",
                                 description="商品一级分类名称，如电子产品、服装"),
            DimensionPropertyDef(column="sub_category_id", name="subCategoryId", caption="二级品类ID"),
            DimensionPropertyDef(column="sub_category_name", name="subCategoryName", caption="二级品类名称"),
            DimensionPropertyDef(column="brand", caption="品牌", description="商品品牌名称"),
            DimensionPropertyDef(column="unit_price", name="unitPrice", caption="商品售价", data_type="MONEY"),
            DimensionPropertyDef(column="unit_cost", name="unitCost", caption="商品成本", data_type="MONEY"),
        ],
    )


def _dim_customer(caption: str = "客户") -> DimensionJoinDef:
    return DimensionJoinDef(
        name="customer",
        table_name="dim_customer",
        foreign_key="customer_key",
        primary_key="customer_key",
        caption_column="customer_name",
        caption=caption,
        alias="dc",
        properties=[
            DimensionPropertyDef(column="customer_id", name="customerId", caption="客户ID"),
            DimensionPropertyDef(column="customer_type", name="customerType", caption="客户类型",
                                 description="客户类型：个人/企业"),
            DimensionPropertyDef(column="gender", caption="性别"),
            DimensionPropertyDef(column="age_group", name="ageGroup", caption="年龄段",
                                 description="18-25/26-35/36-45/46+"),
            DimensionPropertyDef(column="province", caption="省份"),
            DimensionPropertyDef(column="city", caption="城市"),
            DimensionPropertyDef(column="member_level", name="memberLevel", caption="会员等级",
                                 description="普通/银卡/金卡/钻石"),
        ],
    )


def _dim_store(caption: str = "门店") -> DimensionJoinDef:
    return DimensionJoinDef(
        name="store",
        table_name="dim_store",
        foreign_key="store_key",
        primary_key="store_key",
        caption_column="store_name",
        caption=caption,
        alias="ds",
        properties=[
            DimensionPropertyDef(column="store_id", name="storeId", caption="门店ID"),
            DimensionPropertyDef(column="store_type", name="storeType", caption="门店类型",
                                 description="直营店/加盟店/旗舰店"),
            DimensionPropertyDef(column="province", caption="省份"),
            DimensionPropertyDef(column="city", caption="城市"),
        ],
    )


def _dim_channel(caption: str = "渠道") -> DimensionJoinDef:
    return DimensionJoinDef(
        name="channel",
        table_name="dim_channel",
        foreign_key="channel_key",
        primary_key="channel_key",
        caption_column="channel_name",
        caption=caption,
        alias="dch",
        properties=[
            DimensionPropertyDef(column="channel_id", name="channelId", caption="渠道ID"),
            DimensionPropertyDef(column="channel_type", name="channelType", caption="渠道类型",
                                 description="线上/线下"),
            DimensionPropertyDef(column="platform", caption="平台", description="淘宝/京东/线下门店"),
        ],
    )


def _dim_promotion(caption: str = "促销活动") -> DimensionJoinDef:
    return DimensionJoinDef(
        name="promotion",
        table_name="dim_promotion",
        foreign_key="promotion_key",
        primary_key="promotion_key",
        caption_column="promotion_name",
        caption=caption,
        alias="dpm",
        properties=[
            DimensionPropertyDef(column="promotion_id", name="promotionId", caption="促销ID"),
            DimensionPropertyDef(column="promotion_type", name="promotionType", caption="促销类型",
                                 description="满减/折扣/赠品"),
            DimensionPropertyDef(column="discount_rate", name="discountRate", caption="折扣率",
                                 data_type="NUMBER"),
        ],
    )


# ==================== FactSalesModel (aligned with Java FactSalesModel.tm) ====================

def create_fact_sales_model() -> DbTableModelImpl:
    """FactSalesModel — 销售事实表（订单明细）。

    Aligned with Java: foggy-dataset-demo/templates/ecommerce/model/FactSalesModel.tm
    6 dimension JOINs: date, product, customer, store, channel, promotion
    """
    return DbTableModelImpl(
        name="FactSalesModel",
        alias="销售明细查询",
        description="销售事实表查询模型，支持按日期、商品、客户、门店、渠道、促销等维度查询",
        source_table="fact_sales",
        source_schema=None,

        # Dimension JOINs (star schema)
        dimension_joins=[
            _dim_date("salesDate", "销售日期", "订单发生的日期"),
            _dim_product("商品"),
            _dim_customer("客户"),
            _dim_store("门店"),
            _dim_channel("渠道"),
            _dim_promotion("促销活动"),
        ],

        # Fact table own dimensions (properties)
        dimensions={
            "orderId": DbModelDimensionImpl(
                name="orderId", column="order_id", alias="订单ID",
                dimension_type=DimensionType.REGULAR,
            ),
            "orderLineNo": DbModelDimensionImpl(
                name="orderLineNo", column="order_line_no", alias="订单行号",
                dimension_type=DimensionType.REGULAR,
            ),
            "orderStatus": DbModelDimensionImpl(
                name="orderStatus", column="order_status", alias="订单状态",
                dimension_type=DimensionType.REGULAR,
                description="COMPLETED/PAID/PENDING/SHIPPED",
            ),
            "paymentMethod": DbModelDimensionImpl(
                name="paymentMethod", column="payment_method", alias="支付方式",
                dimension_type=DimensionType.REGULAR,
                description="ALIPAY/WECHAT/CARD/CASH",
            ),
        },

        # Measures
        measures={
            "quantity": DbModelMeasureImpl(
                name="quantity", column="quantity", alias="销售数量",
                aggregation=AggregationType.SUM,
            ),
            "salesAmount": DbModelMeasureImpl(
                name="salesAmount", column="sales_amount", alias="销售金额",
                aggregation=AggregationType.SUM,
            ),
            "costAmount": DbModelMeasureImpl(
                name="costAmount", column="cost_amount", alias="成本金额",
                aggregation=AggregationType.SUM,
            ),
            "profitAmount": DbModelMeasureImpl(
                name="profitAmount", column="profit_amount", alias="利润金额",
                aggregation=AggregationType.SUM,
            ),
            "discountAmount": DbModelMeasureImpl(
                name="discountAmount", column="discount_amount", alias="折扣金额",
                aggregation=AggregationType.SUM,
            ),
            "taxAmount": DbModelMeasureImpl(
                name="taxAmount", column="tax_amount", alias="税额",
                aggregation=AggregationType.SUM,
            ),
            "uniqueCustomers": DbModelMeasureImpl(
                name="uniqueCustomers", column="customer_key", alias="独立客户数",
                aggregation=AggregationType.COUNT_DISTINCT,
            ),
            "orderCount": DbModelMeasureImpl(
                name="orderCount", column="order_id", alias="订单数",
                aggregation=AggregationType.COUNT_DISTINCT,
            ),
        },
    )


# ==================== FactOrderModel ====================

def create_fact_order_model() -> DbTableModelImpl:
    """FactOrderModel — 订单事实表（订单头）。"""
    return DbTableModelImpl(
        name="FactOrderModel",
        alias="订单查询",
        description="订单事实表查询模型，支持按日期、客户、门店、渠道等维度查询",
        source_table="fact_order",
        source_schema=None,
        dimension_joins=[
            _dim_date("orderDate", "订单日期", "订单创建的日期"),
            _dim_customer("客户"),
            _dim_store("门店"),
            _dim_channel("渠道"),
            _dim_promotion("促销活动"),
        ],
        dimensions={
            "orderId": DbModelDimensionImpl(
                name="orderId", column="order_id", alias="订单ID",
                dimension_type=DimensionType.REGULAR,
            ),
            "orderStatus": DbModelDimensionImpl(
                name="orderStatus", column="order_status", alias="订单状态",
                dimension_type=DimensionType.REGULAR,
            ),
        },
        measures={
            "totalAmount": DbModelMeasureImpl(
                name="totalAmount", column="total_amount", alias="订单总额",
                aggregation=AggregationType.SUM,
            ),
            "totalQuantity": DbModelMeasureImpl(
                name="totalQuantity", column="total_quantity", alias="总数量",
                aggregation=AggregationType.SUM,
            ),
            "totalDiscount": DbModelMeasureImpl(
                name="totalDiscount", column="discount_amount", alias="总折扣",
                aggregation=AggregationType.SUM,
            ),
            "payAmount": DbModelMeasureImpl(
                name="payAmount", column="pay_amount", alias="应付金额",
                aggregation=AggregationType.SUM,
            ),
        },
    )


# ==================== FactPaymentModel ====================

def create_fact_payment_model() -> DbTableModelImpl:
    """FactPaymentModel — 支付事实表。"""
    return DbTableModelImpl(
        name="FactPaymentModel",
        alias="支付查询",
        description="支付事实表查询模型",
        source_table="fact_payment",
        source_schema=None,
        dimension_joins=[
            _dim_date("payDate", "支付日期", "支付发生的日期"),
            _dim_customer("客户"),
        ],
        dimensions={
            "paymentId": DbModelDimensionImpl(
                name="paymentId", column="payment_id", alias="支付业务ID",
                dimension_type=DimensionType.REGULAR,
            ),
            "orderId": DbModelDimensionImpl(
                name="orderId", column="order_id", alias="订单ID",
                dimension_type=DimensionType.REGULAR,
            ),
            "payMethod": DbModelDimensionImpl(
                name="payMethod", column="pay_method", alias="支付方式",
                dimension_type=DimensionType.REGULAR,
            ),
            "payStatus": DbModelDimensionImpl(
                name="payStatus", column="pay_status", alias="支付状态",
                dimension_type=DimensionType.REGULAR,
            ),
        },
        measures={
            "payAmount": DbModelMeasureImpl(
                name="payAmount", column="pay_amount", alias="支付金额",
                aggregation=AggregationType.SUM,
            ),
        },
    )


# ==================== FactReturnModel ====================

def create_fact_return_model() -> DbTableModelImpl:
    """FactReturnModel — 退货事实表。"""
    return DbTableModelImpl(
        name="FactReturnModel",
        alias="退货查询",
        description="退货事实表查询模型",
        source_table="fact_return",
        source_schema=None,
        dimension_joins=[
            _dim_date("returnDate", "退货日期", "退货申请的日期"),
            _dim_product("商品"),
            _dim_customer("客户"),
            _dim_store("门店"),
        ],
        dimensions={
            "returnId": DbModelDimensionImpl(
                name="returnId", column="return_id", alias="退货业务ID",
                dimension_type=DimensionType.REGULAR,
            ),
            "orderId": DbModelDimensionImpl(
                name="orderId", column="order_id", alias="原订单ID",
                dimension_type=DimensionType.REGULAR,
            ),
            "returnReason": DbModelDimensionImpl(
                name="returnReason", column="return_reason", alias="退货原因",
                dimension_type=DimensionType.REGULAR,
            ),
            "returnStatus": DbModelDimensionImpl(
                name="returnStatus", column="return_status", alias="退货状态",
                dimension_type=DimensionType.REGULAR,
            ),
        },
        measures={
            "returnQuantity": DbModelMeasureImpl(
                name="returnQuantity", column="return_quantity", alias="退货数量",
                aggregation=AggregationType.SUM,
            ),
            "returnAmount": DbModelMeasureImpl(
                name="returnAmount", column="return_amount", alias="退款金额",
                aggregation=AggregationType.SUM,
            ),
        },
    )


# ==================== FactInventorySnapshotModel ====================

def create_fact_inventory_model() -> DbTableModelImpl:
    """FactInventorySnapshotModel — 库存快照表。"""
    return DbTableModelImpl(
        name="FactInventorySnapshotModel",
        alias="库存查询",
        description="库存快照查询模型",
        source_table="fact_inventory_snapshot",
        source_schema=None,
        dimension_joins=[
            _dim_date("snapshotDate", "快照日期", "库存快照日期"),
            _dim_product("商品"),
            _dim_store("仓库/门店"),
        ],
        dimensions={},
        measures={
            "quantityOnHand": DbModelMeasureImpl(
                name="quantityOnHand", column="quantity_on_hand", alias="在手库存",
                aggregation=AggregationType.SUM,
            ),
            "quantityReserved": DbModelMeasureImpl(
                name="quantityReserved", column="quantity_reserved", alias="预留库存",
                aggregation=AggregationType.SUM,
            ),
            "quantityAvailable": DbModelMeasureImpl(
                name="quantityAvailable", column="quantity_available", alias="可用库存",
                aggregation=AggregationType.SUM,
            ),
        },
    )


# ==================== Aggregate ====================

def create_all_ecommerce_models() -> Dict[str, DbTableModelImpl]:
    """Create all e-commerce demo models (aligned with Java application.yml)."""
    return {
        "FactSalesModel": create_fact_sales_model(),
        "FactOrderModel": create_fact_order_model(),
        "FactPaymentModel": create_fact_payment_model(),
        "FactReturnModel": create_fact_return_model(),
        "FactInventorySnapshotModel": create_fact_inventory_model(),
    }
