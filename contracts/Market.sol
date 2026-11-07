// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

contract TestToken {
    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    uint256 public immutable totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 amount);
    event Approval(address indexed owner, address indexed spender, uint256 amount);

    constructor(bool risk, uint256 supply) {
        name = risk ? "Lab Risk" : "Lab Synthetic Dollar";
        symbol = risk ? "RISK" : "sUSD";
        totalSupply = supply;
        balanceOf[msg.sender] = supply;
        emit Transfer(address(0), msg.sender, supply);
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 approved = allowance[from][msg.sender];
        if (approved != type(uint256).max) {
            allowance[from][msg.sender] = approved - amount;
        }
        _transfer(from, to, amount);
        return true;
    }

    function _transfer(address from, address to, uint256 amount) private {
        require(to != address(0), "zero recipient");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
    }
}

/// @notice V2-style demo for the two known TestToken contracts.
contract DemoPool {
    TestToken public immutable risk;
    TestToken public immutable susd;
    address public immutable provider;
    uint256 public reserveRisk;
    uint256 public reserveSusd;

    event Seed(uint256 riskIn, uint256 susdIn);
    event Swap(address indexed trader, bool riskIn, uint256 amountIn, uint256 amountOut,
               uint256 reserveRiskAfter, uint256 reserveSusdAfter);

    constructor(TestToken riskToken, TestToken susdToken) {
        require(address(riskToken) != address(susdToken), "same token");
        risk = riskToken;
        susd = susdToken;
        provider = msg.sender;
    }

    function seed(uint256 riskIn, uint256 susdIn) external {
        require(msg.sender == provider && reserveRisk == 0, "seed once");
        require(riskIn > 0 && susdIn > 0, "empty deposit");
        require(risk.transferFrom(msg.sender, address(this), riskIn));
        require(susd.transferFrom(msg.sender, address(this), susdIn));
        reserveRisk = riskIn;
        reserveSusd = susdIn;
        emit Seed(riskIn, susdIn);
    }

    function quote(bool riskIn, uint256 amountIn) public view returns (uint256) {
        uint256 x = riskIn ? reserveRisk : reserveSusd;
        uint256 y = riskIn ? reserveSusd : reserveRisk;
        require(x > 0 && y > 0, "unseeded");
        uint256 weighted = amountIn * 997;
        return weighted * y / (x * 1000 + weighted);
    }

    function swap(bool riskIn, uint256 amountIn, uint256 minOut) external returns (uint256 amountOut) {
        amountOut = quote(riskIn, amountIn);
        require(amountOut > 0 && amountOut >= minOut, "min out");
        if (riskIn) {
            reserveRisk += amountIn;
            reserveSusd -= amountOut;
            require(risk.transferFrom(msg.sender, address(this), amountIn));
            require(susd.transfer(msg.sender, amountOut));
        } else {
            reserveSusd += amountIn;
            reserveRisk -= amountOut;
            require(susd.transferFrom(msg.sender, address(this), amountIn));
            require(risk.transfer(msg.sender, amountOut));
        }
        emit Swap(msg.sender, riskIn, amountIn, amountOut, reserveRisk, reserveSusd);
    }
}
